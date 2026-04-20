import { useEffect, useState, type RefObject } from "react";
import type { Element } from "../types/paper";
import type { HighlightColor, TextHighlight } from "../types/highlight";
import HighlightableText from "./HighlightableText";

type Props = {
  paperId: number;
  element: Element;
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
};

export default function ElementRow({
  paperId,
  element,
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
}: Props) {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(element.text || "");
  const [draftIntroText, setDraftIntroText] = useState(element.intro_text || "");
  const [draftItems, setDraftItems] = useState<string[]>(element.items || []);
  const [saving, setSaving] = useState(false);
  const [showInsertBox, setShowInsertBox] = useState(false);
  const [insertText, setInsertText] = useState("");
  const [showFlash, setShowFlash] = useState(false);

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

  const canEdit = currentLanguage === "en";

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

  return (
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
                    disabled={saving}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setDraftText(element.text || "");
                      setEditing(false);
                    }}
                    disabled={saving}
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
                        disabled={saving}
                      >
                        {saving ? "Adding..." : "Add below"}
                      </button>
                      <button
                        onClick={() => {
                          setInsertText("");
                          setShowInsertBox(false);
                        }}
                        disabled={saving}
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
                      onClick={async (e) => {
                        e.stopPropagation();
                        const ok = window.confirm("Delete this paragraph?");
                        if (!ok) return;

                        try {
                          setSaving(true);
                          await onDeleteParagraph(element.paragraph_id);
                        } finally {
                          setSaving(false);
                        }
                      }}
                      disabled={saving}
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
                        disabled={saving}
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
                    disabled={saving}
                  >
                    Add item
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      void saveBulletEdit();
                    }}
                    disabled={saving}
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
                    disabled={saving}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                {element.intro_text && (
                  <div className="bullet-intro">
                    <HighlightableText
                      paperId={paperId}
                      paragraphId={element.paragraph_id}
                      scope="paragraph"
                      fieldName="intro_text"
                      language={currentLanguage}
                      text={element.intro_text}
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
                        disabled={saving}
                      >
                        {saving ? "Adding..." : "Add below"}
                      </button>
                      <button
                        onClick={() => {
                          setInsertText("");
                          setShowInsertBox(false);
                        }}
                        disabled={saving}
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
                      onClick={async (e) => {
                        e.stopPropagation();
                        const ok = window.confirm("Delete this bullet list?");
                        if (!ok) return;

                        try {
                          setSaving(true);
                          await onDeleteParagraph(element.paragraph_id);
                        } finally {
                          setSaving(false);
                        }
                      }}
                      disabled={saving}
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
  );
}
           
