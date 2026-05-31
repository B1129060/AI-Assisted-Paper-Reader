import { useEffect, useState, type MouseEvent, type RefObject } from "react";
import type { Element } from "../types/paper";
import type { HighlightColor, TextHighlight } from "../types/highlight";
import HighlightableText from "./HighlightableText";

type Props = {
  paperId: number;
  element: Element;
  hoverElement?: Element | null;
  headingRef?: RefObject<HTMLDivElement | null>;
  currentLanguage: "en" | "zh";
  highlightColor: HighlightColor;
  textHighlights: TextHighlight[];
  onTextHighlightCreated: (highlight: TextHighlight) => void;
  onTextHighlightDeleted: (highlightId: number) => void;
  onSaveParagraph: (paragraphId: number, text: string) => Promise<void>;
  onSaveBulletList: (paragraphId: number, introText: string, items: string[]) => Promise<void>;
  onInsertParagraphAfter: (paragraphId: number, text: string) => Promise<void>;
  onDeleteParagraph: (paragraphId: number) => Promise<void>;
  onSelectElement?: (element: Element) => void;
  flashToken?: number;
  isFlashing?: boolean;
  textHighlightMode: boolean;
  editDisabled?: boolean;
};

type ElementWithZh = Element & {
  text_zh?: string | null;
  summary_zh?: string | null;
  key_points_zh?: string[] | null;
  intro_text_zh?: string | null;
  items_zh?: string[] | null;
};

export default function ElementRow({
  paperId,
  element,
  hoverElement = null,
  headingRef,
  currentLanguage,
  highlightColor,
  textHighlights,
  onTextHighlightCreated,
  onTextHighlightDeleted,
  onSaveParagraph,
  onSaveBulletList,
  onInsertParagraphAfter,
  onDeleteParagraph,
  onSelectElement,
  isFlashing,
  flashToken,
  textHighlightMode,
  editDisabled = false,
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(element.text || "");
  const [draftIntroText, setDraftIntroText] = useState(element.intro_text || "");
  const [draftItems, setDraftItems] = useState<string[]>(element.items || []);
  const [saving, setSaving] = useState(false);
  const [showInsertBox, setShowInsertBox] = useState(false);
  const [insertText, setInsertText] = useState("");
  const [showFlash, setShowFlash] = useState(false);
  const [deleteConfirmType, setDeleteConfirmType] = useState<"paragraph" | "bullet_list" | null>(null);

  useEffect(() => {
    setDraftText(element.text || "");
    setDraftIntroText(element.intro_text || "");
    setDraftItems(element.items || []);
  }, [element.text, element.intro_text, element.items]);

  useEffect(() => {
    if (!isFlashing) return;

    setShowFlash(true);

    const timer = window.setTimeout(() => {
      setShowFlash(false);
    }, 1200);

    return () => window.clearTimeout(timer);
  }, [isFlashing, flashToken]);

  useEffect(() => {
    if (!editDisabled) return;

    setEditing(false);
    setShowInsertBox(false);
    setDeleteConfirmType(null);
  }, [editDisabled]);

  if (element.type === "heading" && element.level !== "section") {
    return null;
  }

  if (element.type === "heading") {
    return (
      <div className="row heading-row" ref={headingRef}>
        <div className="cell heading-cell">
          <h2>{element.text}</h2>
        </div>
      </div>
    );
  }

  const canEdit = currentLanguage === "en" && !editDisabled;
  const elementWithZh = element as ElementWithZh;
  const hoverElementWithZh = hoverElement as ElementWithZh | null;

  function getHoverTranslation(primary?: string | null, fallback?: string | null) {
    if (currentLanguage !== "en") return null;
    return primary || fallback || null;
  }

  function getHoverTranslationItem(
    primaryValues: string[] | null | undefined,
    fallbackValues: string[] | null | undefined,
    index: number
  ) {
    if (currentLanguage !== "en") return null;
    return primaryValues?.[index] || fallbackValues?.[index] || null;
  }

  function handleRowClick() {
    const selected = window.getSelection()?.toString().trim();
    if (selected) return;
    onSelectElement?.(element);
  }

  async function saveParagraphEdit() {
    try {
      setSaving(true);
      await onSaveParagraph(element.paragraph_id, draftText);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  async function saveBulletEdit() {
    try {
      setSaving(true);
      await onSaveBulletList(element.paragraph_id, draftIntroText, draftItems);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  function updateItem(index: number, value: string) {
    setDraftItems((prev) => prev.map((item, i) => (i === index ? value : item)));
  }

  function addItem() {
    setDraftItems((prev) => [...prev, ""]);
  }

  function removeItem(index: number) {
    setDraftItems((prev) => prev.filter((_, i) => i !== index));
  }

  function getDisplayIntroText() {
    if (currentLanguage === "zh") {
      return (
        elementWithZh.intro_text_zh ||
        hoverElementWithZh?.intro_text ||
        element.intro_text ||
        ""
      );
    }

    return element.intro_text || "";
  }

  function openDeleteConfirm(
    e: MouseEvent<HTMLButtonElement>,
    type: "paragraph" | "bullet_list"
  ) {
    e.stopPropagation();
    setDeleteConfirmType(type);
  }

  async function confirmDeleteElement() {
    try {
      setSaving(true);
      await onDeleteParagraph(element.paragraph_id);
      setDeleteConfirmType(null);
    } finally {
      setSaving(false);
    }
  }

  const displayIntroText = getDisplayIntroText();
  const deleteTitle =
    deleteConfirmType === "bullet_list" ? "刪除條列段落" : "刪除段落";
  const deleteMessage =
    deleteConfirmType === "bullet_list"
      ? "是否確定要刪除此條列段落？"
      : "是否確定要刪除此段落？";

  return (
    <>
    <div
      className={`row content-row ${showFlash ? "active-row" : ""}`}
      data-paragraph-id={element.paragraph_id}
      onClick={handleRowClick}
      style={{ cursor: "pointer" }}
    >
      <div className="cell keypoints-cell">
        {element.key_points && element.key_points.length > 0 ? (
          element.key_points.map((kp, idx) => (
            <div key={idx} className="keypoint-item">
              •{" "}
              <HighlightableText
                paperId={paperId}
                paragraphId={element.paragraph_id}
                scope="paragraph"
                fieldName="key_points"
                itemIndex={idx}
                language={currentLanguage}
                text={kp}
                hoverTranslation={getHoverTranslationItem(hoverElementWithZh?.key_points, elementWithZh.key_points_zh, idx)}
                color={highlightColor}
                highlights={textHighlights}
                enabled={textHighlightMode}
                onCreated={onTextHighlightCreated}
                onDeleted={onTextHighlightDeleted}
              />
            </div>
          ))
        ) : (
          <div className="placeholder-text">—</div>
        )}
      </div>

      <div className="cell summary-cell">
        {element.summary ? (
          <HighlightableText
            paperId={paperId}
            paragraphId={element.paragraph_id}
            scope="paragraph"
            fieldName="summary"
            language={currentLanguage}
            text={element.summary}
            hoverTranslation={getHoverTranslation(hoverElementWithZh?.summary, elementWithZh.summary_zh)}
            color={highlightColor}
            highlights={textHighlights}
            enabled={textHighlightMode}
            onCreated={onTextHighlightCreated}
            onDeleted={onTextHighlightDeleted}
          />
        ) : (
          <div className="placeholder-text">—</div>
        )}
      </div>

      <div className="cell text-cell">
        {element.type === "paragraph" && (
          <>
            {editing ? (
              <>
                <textarea
                  className="edit-textarea"
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                <div className="edit-actions">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      void saveParagraphEdit();
                    }}
                    disabled={saving || editDisabled}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDraftText(element.text || "");
                      setEditing(false);
                    }}
                    disabled={saving || editDisabled}
                  >
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <>
                <HighlightableText
                  paperId={paperId}
                  paragraphId={element.paragraph_id}
                  scope="paragraph"
                  fieldName="text"
                  language={currentLanguage}
                  text={element.text || "—"}
                  hoverTranslation={getHoverTranslation(hoverElementWithZh?.text, elementWithZh.text_zh)}
                  color={highlightColor}
                  highlights={textHighlights}
                  enabled={textHighlightMode}
                  onCreated={onTextHighlightCreated}
                  onDeleted={onTextHighlightDeleted}
                />

                {showInsertBox && (
                  <div
                    className="insert-paragraph-block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <textarea
                      className="edit-textarea"
                      value={insertText}
                      onChange={(e) => setInsertText(e.target.value)}
                      placeholder="New paragraph text"
                    />
                    <div className="edit-actions">
                      <button
                        onClick={async () => {
                          try {
                            setSaving(true);
                            await onInsertParagraphAfter(element.paragraph_id, insertText);
                            setInsertText("");
                            setShowInsertBox(false);
                          } finally {
                            setSaving(false);
                          }
                        }}
                        disabled={saving || editDisabled}
                      >
                        {saving ? "Adding..." : "Add below"}
                      </button>
                      <button
                        onClick={() => {
                          setInsertText("");
                          setShowInsertBox(false);
                        }}
                        disabled={saving || editDisabled}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {canEdit && (
                  <div className="edit-actions">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing(true);
                      }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowInsertBox((prev) => !prev);
                      }}
                    >
                      {showInsertBox ? "Close insert" : "Insert below"}
                    </button>
                    <button
                      onClick={(e) => openDeleteConfirm(e, "paragraph")}
                      disabled={saving || editDisabled}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {element.type === "bullet_list" && (
          <>
            {editing ? (
              <div
                className="bullet-edit-block"
                onClick={(e) => e.stopPropagation()}
              >
                <textarea
                  className="edit-textarea"
                  value={draftIntroText}
                  onChange={(e) => setDraftIntroText(e.target.value)}
                  placeholder="Intro text"
                />

                <div className="bullet-edit-items">
                  {draftItems.map((item, idx) => (
                    <div key={idx} className="bullet-edit-item-row">
                      <textarea
                        className="edit-textarea bullet-item-textarea"
                        value={item}
                        onChange={(e) => updateItem(idx, e.target.value)}
                        placeholder={`Bullet item ${idx + 1}`}
                      />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeItem(idx);
                        }}
                        disabled={saving || editDisabled}
                      >
                        Delete
                      </button>
                    </div>
                  ))}
                </div>

                <div className="edit-actions">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      addItem();
                    }}
                    disabled={saving || editDisabled}
                  >
                    Add item
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      void saveBulletEdit();
                    }}
                    disabled={saving || editDisabled}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDraftIntroText(element.intro_text || "");
                      setDraftItems(element.items || []);
                      setEditing(false);
                    }}
                    disabled={saving || editDisabled}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                {displayIntroText && (
                  <div className="bullet-intro">
                    <HighlightableText
                      paperId={paperId}
                      paragraphId={element.paragraph_id}
                      scope="paragraph"
                      fieldName="intro_text"
                      language={currentLanguage}
                      text={displayIntroText}
                      hoverTranslation={getHoverTranslation(hoverElementWithZh?.intro_text, elementWithZh.intro_text_zh)}
                      color={highlightColor}
                      highlights={textHighlights}
                      enabled={textHighlightMode}
                      onCreated={onTextHighlightCreated}
                      onDeleted={onTextHighlightDeleted}
                    />
                  </div>
                )}

                <ul className="bullet-items">
                  {element.items?.map((item, idx) => (
                    <li key={idx}>
                      <HighlightableText
                        paperId={paperId}
                        paragraphId={element.paragraph_id}
                        scope="paragraph"
                        fieldName="item"
                        itemIndex={idx}
                        language={currentLanguage}
                        text={item}
                        hoverTranslation={getHoverTranslationItem(hoverElementWithZh?.items, elementWithZh.items_zh, idx)}
                        color={highlightColor}
                        highlights={textHighlights}
                        enabled={textHighlightMode}
                        onCreated={onTextHighlightCreated}
                        onDeleted={onTextHighlightDeleted}
                      />
                    </li>
                  ))}
                </ul>

                {showInsertBox && (
                  <div
                    className="insert-paragraph-block"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <textarea
                      className="edit-textarea"
                      value={insertText}
                      onChange={(e) => setInsertText(e.target.value)}
                      placeholder="New paragraph text"
                    />
                    <div className="edit-actions">
                      <button
                        onClick={async () => {
                          try {
                            setSaving(true);
                            await onInsertParagraphAfter(element.paragraph_id, insertText);
                            setInsertText("");
                            setShowInsertBox(false);
                          } finally {
                            setSaving(false);
                          }
                        }}
                        disabled={saving || editDisabled}
                      >
                        {saving ? "Adding..." : "Add below"}
                      </button>
                      <button
                        onClick={() => {
                          setInsertText("");
                          setShowInsertBox(false);
                        }}
                        disabled={saving || editDisabled}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {canEdit && (
                  <div className="edit-actions">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditing(true);
                      }}
                    >
                      Edit
                    </button>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowInsertBox((prev) => !prev);
                      }}
                    >
                      {showInsertBox ? "Close insert" : "Insert below"}
                    </button>

                    <button
                      onClick={(e) => openDeleteConfirm(e, "bullet_list")}
                      disabled={saving || editDisabled}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>

    {deleteConfirmType && (
      <div
        className="modal-backdrop"
        onClick={(e) => {
          e.stopPropagation();
          if (!saving) setDeleteConfirmType(null);
        }}
      >
        <div
          className="confirm-modal inline-confirm-modal"
          onClick={(e) => e.stopPropagation()}
        >
          <h2>{deleteTitle}</h2>
          <p>{deleteMessage}</p>
          <p className="confirm-warning">這個操作無法復原。</p>

          <div className="confirm-modal-actions">
            <button
              className="modal-secondary-button"
              onClick={() => setDeleteConfirmType(null)}
              disabled={saving || editDisabled}
            >
              Cancel
            </button>
            <button
              className="danger-button"
              onClick={() => void confirmDeleteElement()}
              disabled={saving || editDisabled}
            >
              {saving ? "Deleting..." : "Confirm Delete"}
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}

