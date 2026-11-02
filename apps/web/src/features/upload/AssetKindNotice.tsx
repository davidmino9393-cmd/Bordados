import { MediaType } from '../../contracts/settings';
import type { SourceAsset } from '../../contracts/project';
import { es } from '../../copy/es';

/**
 * Deja claro qué camino sigue lo que se subió: un SVG preparado va directo a la generación;
 * una imagen pasa primero por el análisis de una IA, que se revisa antes de continuar.
 */
export function AssetKindNotice({ asset }: { asset: SourceAsset }) {
  const prepared = asset.media_type === MediaType.Svg;
  return (
    <div className={`asset-kind asset-kind--${prepared ? 'prepared' : 'image'}`}>
      <span className={`badge ${prepared ? 'badge--ok' : 'badge--progress'}`}>
        {prepared ? es.upload.preparedBadge : es.upload.imageBadge}
      </span>
      <span>{prepared ? es.upload.preparedText : es.upload.imageText}</span>
    </div>
  );
}
