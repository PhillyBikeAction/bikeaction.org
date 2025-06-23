import { Injectable } from '@angular/core';
import { Photo } from '@capacitor/camera';
import { Capacitor } from '@capacitor/core';
import { Directory, Filesystem } from '@capacitor/filesystem';
import { Platform } from '@ionic/angular';
import { Storage } from '@ionic/storage-angular';

@Injectable({
  providedIn: 'root',
})
export class PhotoService {
  public photos: UserPhoto[] = [];
  private PHOTO_STORAGE: string = 'photos';

  constructor(
    private platform: Platform,
    private storage: Storage,
  ) {}

  public async savePicture(photo: Photo) {
    const base64Data = await this.readAsBase64(photo);

    const fileName = new Date().getTime() + '.jpeg';
    const savedFile = await Filesystem.writeFile({
      path: fileName,
      data: base64Data,
      directory: Directory.External,
      recursive: true,
    });

    if (this.platform.is('hybrid')) {
      return {
        filepath: fileName,
        webviewPath: Capacitor.convertFileSrc(savedFile.uri),
      };
    } else {
      return {
        filepath: fileName,
        webviewPath: photo.webPath,
      };
    }
  }

  public async savePictureFromBase64(base64Data: string, fileName?: string) {
    if (fileName === undefined) {
      fileName = new Date().getTime() + '.jpeg';
    }
    const savedFile = await Filesystem.writeFile({
      path: fileName,
      data: base64Data,
      directory: Directory.External,
      recursive: true,
    });

    if (this.platform.is('hybrid')) {
      return {
        filepath: fileName,
        webviewPath: Capacitor.convertFileSrc(savedFile.uri),
      };
    } else {
      return {
        filepath: fileName,
        webviewPath: `data:image/jpeg;base64,${base64Data}`,
      };
    }
  }

  public async fetchPicture(filename: string): Promise<UserPhoto> {
    return Filesystem.readFile({
      path: filename,
      directory: Directory.External,
    }).then((readFile) => {
      return new Promise((resolve, reject) => {
        resolve({
          filepath: filename,
          webviewPath: `data:image/jpeg;base64,${readFile.data}`,
        });
      });
    });
  }

  public async readAsBase64(photo: Photo) {
    if (this.platform.is('hybrid')) {
      const file = await Filesystem.readFile({
        path: photo.path!,
      });

      return file.data;
    } else {
      const response = await fetch(photo.webPath!);
      const blob = await response.blob();

      return (await this.convertBlobToBase64(blob)) as string;
    }
  }

  public async deletePicture(filename: string) {
    await Filesystem.deleteFile({
      path: filename,
      directory: Directory.External,
    });
  }

  convertBlobToBase64 = (blob: Blob) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = reject;
      reader.onload = () => {
        resolve(reader.result);
      };
      reader.readAsDataURL(blob);
    });
}

export interface UserPhoto {
  filepath: string;
  webviewPath: string;
}
