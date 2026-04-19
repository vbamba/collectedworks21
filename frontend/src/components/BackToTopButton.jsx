// frontend/src/components/BackToTopButton.jsx
// MOD: Floating back-to-top button with smooth scroll.

import React, { useEffect, useState } from "react";

const BackToTopButton = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => {
      setVisible(window.scrollY > 400);
    };
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!visible) return null;

  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className="btn btn-light"
      style={{
        position: "fixed",
        bottom: "20px",
        right: "20px",
        borderRadius: "50%",
        width: "48px",
        height: "48px",
        boxShadow: "0 2px 6px rgba(0,0,0,0.4)"
      }}
      aria-label="Back to top"
    >
      ↑
    </button>
  );
};

export default BackToTopButton;
