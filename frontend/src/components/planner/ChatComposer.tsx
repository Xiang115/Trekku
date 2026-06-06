import { useState } from "react";
import Icon from "../../icons/Icon";

export default function ChatComposer({
  onSend,
  disabled,
}: {
  onSend: (text: string) => void;
  disabled: boolean;
}) {
  const [text, setText] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const value = text.trim();
    if (!value || disabled) return;
    onSend(value);
    setText("");
  };

  return (
    <form className="search-box" onSubmit={submit}>
      <label htmlFor="chatInput">Trip request</label>
      <div className={`search-row${disabled ? " is-busy" : ""}`}>
        <Icon name="search" />
        <input
          id="chatInput"
          name="chatInput"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Describe your trip, or answer Trekku's question…"
          autoComplete="off"
        />
        <button type="submit" disabled={disabled}>
          {disabled ? "Sending…" : "Send"}
        </button>
      </div>
    </form>
  );
}
