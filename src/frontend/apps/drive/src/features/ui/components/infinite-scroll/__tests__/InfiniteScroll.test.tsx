import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { InfiniteScroll } from "../InfiniteScroll";

const renderedLoaders: Array<Record<string, unknown>> = [];

jest.mock("@gouvfr-lasuite/cunningham-react", () => ({
  Loader: (props: { size?: string; "aria-label"?: string }) => {
    renderedLoaders.push(props as Record<string, unknown>);
    return <div>loader:{props.size}:{props["aria-label"]}</div>;
  },
  useCunningham: () => ({
    t: (key: string) => key,
  }),
}));

describe("InfiniteScroll", () => {
  beforeEach(() => {
    renderedLoaders.length = 0;
  });

  it("renders children and the shared trigger container", () => {
    const html = renderToStaticMarkup(
      <InfiniteScroll
        className="infinite-scroll-host"
        fetchNextPage={jest.fn()}
        hasNextPage={true}
        isFetchingNextPage={false}
      >
        <div>child-content</div>
      </InfiniteScroll>,
    );

    expect(html).toContain("child-content");
    expect(html).toContain("infinite-scroll__trigger");
    expect(html).toContain("infinite-scroll-host");
    expect(renderedLoaders).toHaveLength(0);
  });

  it("renders the default loading indicator when fetching", () => {
    const html = renderToStaticMarkup(
      <InfiniteScroll
        fetchNextPage={jest.fn()}
        hasNextPage={true}
        isFetchingNextPage={true}
      >
        <div>child-content</div>
      </InfiniteScroll>,
    );

    expect(html).toContain("loader:small:components.datagrid.loader_aria");
    expect(html).toContain("infinite-scroll__loading-component");
    expect(renderedLoaders).toHaveLength(1);
  });

  it("prefers a provided loading component over the default one", () => {
    const html = renderToStaticMarkup(
      <InfiniteScroll
        fetchNextPage={jest.fn()}
        hasNextPage={true}
        isFetchingNextPage={true}
        loadingComponent={<div>custom-loading</div>}
      >
        <div>child-content</div>
      </InfiniteScroll>,
    );

    expect(html).toContain("custom-loading");
    expect(renderedLoaders).toHaveLength(0);
  });
});
