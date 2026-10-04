import { ImagePlus, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

type DropzoneProps = {
  label: string;
  hint: string;
  file: File | null;
  onChange: (file: File | null) => void;
};

export function Dropzone({ label, hint, file, onChange }: DropzoneProps) {
  const [preview, setPreview] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setPreview(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  return (
    <label className={`dropzone${preview ? " has-image" : ""}`}>
      <input
        type="file"
        accept="image/*"
        aria-label={`${label}: ${hint}`}
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      {preview && <span className="dropzone-label">{label}</span>}
      {preview ? (
        <>
          <img src={preview} alt="" />
          <span className="button button-secondary dropzone-replace">
            <RefreshCw size={14} strokeWidth={1.75} />
            Trocar
          </span>
        </>
      ) : (
        <>
          <ImagePlus size={28} strokeWidth={1.5} />
          <span className="dropzone-title">{label}</span>
          <span>{hint}</span>
        </>
      )}
    </label>
  );
}
