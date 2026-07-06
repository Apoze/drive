import React, {
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { Page } from "react-pdf";
import { AutoSizer, List } from "react-virtualized";
import type { ListRowRenderer, Index } from "react-virtualized";
import { useDebouncedResize } from "./useDebouncedResize";
import { FALLBACK_RATIO, type PageDimensionsMap } from "./usePdfPageDimensions";

const PAGE_GAP = 16;
const BASE_WIDTH = 800;
const PAGE_MARGIN = 32;

export interface PdfPageViewerHandle {
  scrollToPage: (page: number) => void;
}

interface PdfPageViewerProps {
  numPages: number;
  zoom: number;
  onCurrentPageChange: (page: number) => void;
  onClick: (e: React.MouseEvent<HTMLDivElement>) => void;
  pageDimensions: PageDimensionsMap;
  requestPageDimension: (page: number) => void;
  ensurePageDimensions: (pages: number[]) => Promise<PageDimensionsMap>;
}

export function PdfPageViewer({
  numPages,
  zoom,
  onCurrentPageChange,
  onClick,
  pageDimensions,
  requestPageDimension,
  ensurePageDimensions,
  ref,
}: PdfPageViewerProps & { ref?: React.Ref<PdfPageViewerHandle> }) {
  const listRef = useRef<List>(null);
  const prevZoomRef = useRef(zoom);
  const [scrollTop, setScrollTop] = useState(0);
  const listHeightRef = useRef(0);
  const scrollJumpIdRef = useRef(0);

  const size = useDebouncedResize();

  const width = useMemo(() => {
    return BASE_WIDTH + PAGE_MARGIN > size.width
      ? size.width - PAGE_MARGIN
      : BASE_WIDTH;
  }, [size.width]);

  const getRatio = useCallback(
    (index: number) => {
      const dimensions = pageDimensions.get(index + 1);
      return dimensions ? dimensions.h / dimensions.w : FALLBACK_RATIO;
    },
    [pageDimensions],
  );

  const rowHeightForIndex = useCallback(
    (index: number) => {
      const h = width * getRatio(index) * zoom;
      const gap = PAGE_GAP * zoom;
      return index === numPages - 1 ? h + 2 * gap : h + gap;
    },
    [width, getRatio, zoom, numPages],
  );

  // Wrapper around rowHeightForIndex with appropriate signature for react-virtualized.
  const rowHeight = useCallback(
    ({ index }: Index) => rowHeightForIndex(index),
    [rowHeightForIndex],
  );

  // When zoom, width, page dimensions or numPages change, row heights must be recalculated
  // because react-virtualized caches them internally.
  // On zoom change we also scale scrollTop proportionally so the user stays
  // on the same part of the document (e.g. 2x zoom → 2x scroll offset).
  useEffect(() => {
    listRef.current?.recomputeRowHeights();

    if (prevZoomRef.current !== zoom && listRef.current) {
      const ratio = zoom / prevZoomRef.current;
      const newScrollTop = Math.round(scrollTop * ratio);

      listRef.current.scrollToPosition(newScrollTop);
      prevZoomRef.current = zoom;
    }
  }, [zoom, width, pageDimensions, numPages]);

  // Find which page contains the vertical center of the viewport by walking
  // cumulative row heights until we pass the midpoint.
  const currentPage = useMemo(() => {
    if (numPages === 0) return 1;

    const viewportCenter = scrollTop + listHeightRef.current / 2;

    let offset = 0;
    for (let i = 0; i < numPages; i++) {
      const h = rowHeightForIndex(i);
      if (offset + h > viewportCenter) {
        return i + 1;
      }
      offset += h;
    }

    return numPages;
  }, [scrollTop, numPages, rowHeightForIndex]);

  useEffect(() => {
    onCurrentPageChange(currentPage);
  }, [currentPage]);

  const scrollToPage = useCallback(
    (page: number) => {
      scrollJumpIdRef.current += 1;
      const jumpId = scrollJumpIdRef.current;

      const pages: number[] = [];
      for (let i = 1; i <= page; i++) {
        pages.push(i);
      }

      ensurePageDimensions(pages).then((dimensions) => {
        if (scrollJumpIdRef.current !== jumpId || !listRef.current) {
          return;
        }

        let offset = 0;
        for (let i = 0; i < page - 1; i++) {
          const d = dimensions.get(i + 1);
          const ratio = d ? d.h / d.w : FALLBACK_RATIO;
          offset += width * ratio * zoom + PAGE_GAP * zoom;
        }
        listRef.current.scrollToPosition(offset);
      });
    },
    [ensurePageDimensions, width, zoom],
  );

  useImperativeHandle(ref, () => ({ scrollToPage }), [scrollToPage]);

  const handleScroll = useCallback(
    ({
      scrollTop: st,
      clientHeight,
    }: {
      scrollTop: number;
      clientHeight: number;
    }) => {
      listHeightRef.current = clientHeight;
      setScrollTop(st);
    },
    [],
  );

  const handleRowsRendered = useCallback(
    ({
      overscanStartIndex,
      overscanStopIndex,
    }: {
      overscanStartIndex: number;
      overscanStopIndex: number;
    }) => {
      for (let i = overscanStartIndex; i <= overscanStopIndex; i++) {
        requestPageDimension(i + 1);
      }
    },
    [requestPageDimension],
  );

  const rowRenderer: ListRowRenderer = ({ index, key, style }) => {
    const ratio = getRatio(index);
    const pageSkeleton = (
      <div
        className="pdf-preview__page-skeleton pdf-preview__page-skeleton--measured"
        style={{ height: width * ratio * zoom, width: width * zoom }}
      />
    );

    return (
      <div
        key={key}
        className="pdf-preview__page-container"
        style={{
          ...style,
          paddingTop: PAGE_GAP * zoom,
          paddingBottom: index === numPages - 1 ? PAGE_GAP * zoom : 0,
        }}
      >
        <Page
          pageNumber={index + 1}
          width={width}
          scale={zoom}
          loading={pageSkeleton}
        />
      </div>
    );
  };

  return (
    <div className="pdf-preview__container" onClick={onClick}>
      <AutoSizer>
        {({ height, width: autoWidth }) => {
          // When zoomed in the page content may exceed the viewport width.
          // The wrapper div is clamped to the viewport (autoWidth) and scrolls
          // horizontally, while the List itself is sized to the full content
          // width so pages render uncropped.
          const listWidth = Math.max(autoWidth, width * zoom);
          return (
            <div
              style={{
                width: autoWidth,
                height,
              }}
              className="pdf-preview__horizontal-scroll"
            >
              <List
                ref={listRef}
                height={height}
                width={listWidth}
                rowCount={numPages}
                rowHeight={rowHeight}
                estimatedRowSize={
                  width * FALLBACK_RATIO * zoom + PAGE_GAP * zoom
                }
                overscanRowCount={3}
                onScroll={handleScroll}
                onRowsRendered={handleRowsRendered}
                rowRenderer={rowRenderer}
                style={{ outline: "none" }}
              />
            </div>
          );
        }}
      </AutoSizer>
    </div>
  );
}
