// frontend/src/components/InfiniteScrollLoader.jsx
// MOD: Reusable infinite scroll component with manual fallback.

import React, { useEffect, useRef } from "react";

const InfiniteScrollLoader = ({ loading, onLoadMore, manualFallback = false }) => {
  const loaderRef = useRef();

  useEffect(() => {
    if (manualFallback) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loading) {
          onLoadMore();
        }
      },
      { threshold: 1 }
    );
    if (loaderRef.current) observer.observe(loaderRef.current);
    return () => observer.disconnect();
  }, [loading, onLoadMore, manualFallback]);

  return (
    <div className="text-center my-3" ref={manualFallback ? null : loaderRef}>
      {manualFallback && (
        <button className="btn btn-outline-light" onClick={onLoadMore} disabled={loading}>
          {loading ? "Loading..." : "Load More"}
        </button>
      )}
      {!manualFallback && loading && <span>Loading...</span>}
    </div>
  );
};

export default InfiniteScrollLoader;
