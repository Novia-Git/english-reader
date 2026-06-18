import { useEffect, useRef, useCallback } from "react";

/**
 * 偵測使用者在 containerRef 內選取的文字。
 * 同時支援桌機 mouse 與手機 touch。
 * onSelect(word, position) 被觸發，position = { x, y } popup 定位用。
 */
export default function useTextSelection(onSelect) {
  const containerRef = useRef(null);

  const handleSelectionChange = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return;

    const text = sel.toString().trim();
    // 只取第一個完整單字（去標點）
    const word = text.split(/\s+/)[0].replace(/[^a-zA-Z'-]/g, "");
    if (!word || word.length < 2) return;

    // 取得選取範圍的 bounding rect，用於定位 popup
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const position = {
      x: rect.left + rect.width / 2,
      y: rect.top - 8,  // popup 顯示在選字上方
    };

    onSelect(word.toLowerCase(), position);
  }, [onSelect]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    // 桌機：mouseup
    el.addEventListener("mouseup", handleSelectionChange);
    // 手機：touchend
    el.addEventListener("touchend", () => {
      setTimeout(handleSelectionChange, 100); // 讓 selection 完成
    });

    return () => {
      el.removeEventListener("mouseup", handleSelectionChange);
      el.removeEventListener("touchend", handleSelectionChange);
    };
  }, [handleSelectionChange]);

  return containerRef;
}
