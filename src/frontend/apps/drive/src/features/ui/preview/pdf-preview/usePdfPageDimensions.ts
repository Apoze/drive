import { useCallback, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";

export interface PageDimension {
  w: number;
  h: number;
}

export const FALLBACK_RATIO = 1.414;

export type PageDimensionsMap = ReadonlyMap<number, PageDimension>;

export interface UsePdfPageDimensionsResult {
  pageDimensions: PageDimensionsMap;
  requestPageDimension: (page: number) => void;
  ensurePageDimensions: (pages: number[]) => Promise<PageDimensionsMap>;
  setPdf: (pdf: PDFDocumentProxy | null) => void;
}

export function usePdfPageDimensions(): UsePdfPageDimensionsResult {
  const pdfRef = useRef<PDFDocumentProxy | null>(null);
  const inFlightRef = useRef<Map<number, Promise<void>>>(new Map());
  const pageDimensionsRef = useRef<Map<number, PageDimension>>(new Map());
  const [pageDimensions, setPageDimensions] = useState<
    Map<number, PageDimension>
  >(() => new Map());

  const setPdf = useCallback((pdf: PDFDocumentProxy | null) => {
    pdfRef.current = pdf;
    inFlightRef.current = new Map();
    pageDimensionsRef.current = new Map();
    setPageDimensions(new Map());
  }, []);

  const fetchPageDimension = useCallback((page: number): Promise<void> => {
    const pdf = pdfRef.current;
    if (!pdf || pageDimensionsRef.current.has(page)) {
      return Promise.resolve();
    }

    const existing = inFlightRef.current.get(page);
    if (existing) {
      return existing;
    }

    const promise = pdf
      .getPage(page)
      .then((p) => {
        const viewport = p.getViewport({ scale: 1 });
        const next = new Map(pageDimensionsRef.current);
        next.set(page, { w: viewport.width, h: viewport.height });
        pageDimensionsRef.current = next;
        setPageDimensions(next);
      })
      .catch(() => undefined)
      .finally(() => {
        inFlightRef.current.delete(page);
      });

    inFlightRef.current.set(page, promise);
    return promise;
  }, []);

  const requestPageDimension = useCallback(
    (page: number) => {
      void fetchPageDimension(page);
    },
    [fetchPageDimension],
  );

  const ensurePageDimensions = useCallback(
    async (pages: number[]): Promise<PageDimensionsMap> => {
      await Promise.all(pages.map((page) => fetchPageDimension(page)));
      return pageDimensionsRef.current;
    },
    [fetchPageDimension],
  );

  return {
    pageDimensions,
    requestPageDimension,
    ensurePageDimensions,
    setPdf,
  };
}
