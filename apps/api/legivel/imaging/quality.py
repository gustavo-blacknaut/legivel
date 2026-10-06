import cv2
import numpy as np

from legivel.imaging.preprocess import find_document_corners, load_image, resize_long_side


def assess_photo(content: bytes) -> dict:
    image, _ = load_image(content)
    sample = resize_long_side(cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR), 1000)
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    glare = float(np.mean(gray > 248))
    corners = find_document_corners(sample)
    height, width = gray.shape
    warnings = []
    if sharpness < 60:
        warnings.append("A foto pode estar desfocada. Apoie o celular e tente novamente.")
    if brightness < 65:
        warnings.append("Pouca luz. Fotografe em um local mais iluminado.")
    # Large flat white paper can also trigger this heuristic; keep it advisory.
    if glare > 0.3 and sharpness < 100:
        warnings.append("Possível reflexo ou excesso de luz. Mude o ângulo da câmera.")
    if min(image.size) < 600:
        warnings.append("Resolução baixa. Aproxime o documento sem cortar as bordas.")
    if corners is None:
        warnings.append("Bordas não identificadas. Mostre o documento inteiro sobre um fundo contrastante.")
    return {
        "warnings": warnings,
        "corners": [[float(x / width), float(y / height)] for x, y in corners] if corners is not None else [],
        "sharpness": round(sharpness, 1),
        "brightness": round(brightness, 1),
    }
