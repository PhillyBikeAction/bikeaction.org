import { Pipe, PipeTransform } from '@angular/core';
import { Directory, Filesystem } from '@capacitor/filesystem';

function cropDataUrl(
  dataUrl: string,
  x: number,
  y: number,
  width: number,
  height: number,
): Promise<string> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.src = dataUrl;
    image.onload = () => {
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext('2d');
      if (context) {
        context.drawImage(image, x, y, width, height, 0, 0, width, height);
        const croppedDataUrl = canvas.toDataURL();
        resolve(croppedDataUrl);
      } else {
        reject('Could not get 2D rendering context');
      }
    };
    image.onerror = (error) => {
      reject(error);
    };
  });
}

@Pipe({
  name: 'renderImage',
  standalone: true,
})
export class RenderImagePipe implements PipeTransform {
  transform(
    filename: string,
    xmin?: number,
    ymin?: number,
    xmax?: number,
    ymax?: number,
  ): any {
    return Filesystem.readFile({
      path: filename,
      directory: Directory.External,
    }).then((readFile) => {
      const dataUrl = `data:image/jpeg;base64,${readFile.data}`;
      if (
        ymin !== undefined &&
        xmin !== undefined &&
        ymax !== undefined &&
        xmax !== undefined
      ) {
        return cropDataUrl(dataUrl, xmin, ymin, xmax - xmin, ymax - ymin).then(
          (newDataUrl) => {
            return newDataUrl;
          },
        );
      } else {
        return dataUrl;
      }
    });
  }
}
