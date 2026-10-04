import { ArrowDown, ArrowUp, Camera, ImagePlus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

type PagePickerProps = {
  files: File[];
  onChange: (files: File[]) => void;
  maxPages: number;
  labels: string[];
  allowCamera: boolean;
};

const CAPTURE_QUALITY = 0.95;

function Thumbnail({ file }: { file: File }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  return url ? <img src={url} alt="" /> : null;
}

function CameraPanel({ onCapture, onClose }: { onCapture: (file: File) => void; onClose: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [count, setCount] = useState(0);

  useEffect(() => {
    let stream: MediaStream | null = null;
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment", width: { ideal: 3840 }, height: { ideal: 2160 } }, audio: false })
      .then((media) => {
        stream = media;
        if (videoRef.current) videoRef.current.srcObject = media;
      })
      .catch(() => setError("Não foi possível acessar a câmera. Verifique a permissão do navegador."));
    return () => stream?.getTracks().forEach((track) => track.stop());
  }, []);

  const capture = () => {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        setCount((current) => current + 1);
        onCapture(new File([blob], `camera-${Date.now()}.jpg`, { type: "image/jpeg" }));
      },
      "image/jpeg",
      CAPTURE_QUALITY,
    );
  };

  return (
    <div className="camera">
      {error ? <p className="field-error">{error}</p> : <video ref={videoRef} autoPlay playsInline muted />}
      <div className="camera-actions">
        <button className="button" type="button" onClick={capture} disabled={Boolean(error)}>
          <Camera size={16} strokeWidth={1.75} />
          Capturar página
        </button>
        <span className="muted">{count > 0 && `${count} capturada(s)`}</span>
        <button className="button button-secondary" type="button" onClick={onClose}>
          Concluir
        </button>
      </div>
    </div>
  );
}

export function PagePicker({ files, onChange, maxPages, labels, allowCamera }: PagePickerProps) {
  const [cameraOpen, setCameraOpen] = useState(false);
  const cameraAvailable = allowCamera && window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia);
  const remaining = maxPages - files.length;

  const add = (incoming: File[]) => onChange([...files, ...incoming].slice(0, maxPages));
  const remove = (index: number) => onChange(files.filter((_, position) => position !== index));
  const move = (index: number, offset: number) => {
    const next = [...files];
    const [item] = next.splice(index, 1);
    next.splice(index + offset, 0, item);
    onChange(next);
  };

  return (
    <div className="page-picker">
      {files.length > 0 && (
        <ol className="page-list">
          {files.map((file, index) => (
            <li key={`${file.name}-${file.lastModified}-${index}`}>
              <Thumbnail file={file} />
              <span className="page-list-label">{labels[index] ?? `Página ${index + 1}`}</span>
              <span className="page-list-actions">
                {maxPages > 1 && (
                  <>
                    <button className="icon-button" type="button" aria-label="Mover para cima" disabled={index === 0} onClick={() => move(index, -1)}>
                      <ArrowUp size={14} />
                    </button>
                    <button className="icon-button" type="button" aria-label="Mover para baixo" disabled={index === files.length - 1} onClick={() => move(index, 1)}>
                      <ArrowDown size={14} />
                    </button>
                  </>
                )}
                <button className="icon-button" type="button" aria-label="Remover" onClick={() => remove(index)}>
                  <X size={14} />
                </button>
              </span>
            </li>
          ))}
        </ol>
      )}
      {cameraOpen && <CameraPanel onCapture={(file) => add([file])} onClose={() => setCameraOpen(false)} />}
      {remaining > 0 && !cameraOpen && (
        <div className="picker-actions">
          <label className="dropzone dropzone-compact">
            <input
              type="file"
              accept="image/*"
              multiple={maxPages > 1}
              capture={cameraAvailable ? undefined : "environment"}
              onChange={(event) => {
                add(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
            <ImagePlus size={24} strokeWidth={1.5} />
            <span className="dropzone-title">{labels[files.length] ?? (files.length ? "Adicionar páginas" : "Escolher imagens")}</span>
            <span>{maxPages > 1 ? `Até ${maxPages} páginas · arraste ou toque` : "Tirar foto ou escolher arquivo"}</span>
          </label>
          {cameraAvailable && (
            <button className="button button-secondary" type="button" onClick={() => setCameraOpen(true)}>
              <Camera size={16} strokeWidth={1.75} />
              Usar a câmera
            </button>
          )}
        </div>
      )}
    </div>
  );
}
