import { Injectable } from '@angular/core';
import { Photo } from '@capacitor/camera';
import { Capacitor } from '@capacitor/core';
import { Directory, Filesystem } from '@capacitor/filesystem';
import { Platform } from '@ionic/angular';
import { Storage } from '@ionic/storage-angular';

import { PhotoService } from './photo.service';

@Injectable({
  providedIn: 'root',
})
export class ViolationService {
  constructor(
    private photos: PhotoService,
    private storage: Storage,
  ) {}

  sortViolations(): Promise<any[]> {
    return this.history().then((history) => {
      history.sort(function (a, b) {
        var x = new Date(a.time);
        var y = new Date(b.time);
        return x > y ? -1 : x < y ? 1 : 0;
      });
      return history;
    });
  }

  cleanup() {
    this.sortViolations().then((history) => {
      history.slice(20).forEach((violation, index) => {
        console.log(violation);
        this.deleteViolation(violation.id);
      });
    });
  }

  async history(): Promise<any[]> {
    const violationHistory: any[] = [];
    await this.storage.forEach((value, key, index) => {
      if (key.startsWith('violation-')) {
        violationHistory.push(value);
      }
    });
    return violationHistory;
  }

  deleteViolation(violationId: number) {
    let violation = null;
    this.storage.get('violation-' + violationId).then((violation) => {
      this.photos.deletePicture(violation!.image);
      this.photos.deletePicture(violation!.thumbnail);
    });
    this.storage.remove('violation-' + violationId);
  }

  async saveImage(violationId: number) {
    this.storage.get('violation-' + violationId).then((violation) => {
      Filesystem.readFile({
        path: violation.image,
        directory: Directory.External,
      }).then((readFile) => {
        const hiddenElement = document.createElement('a');
        hiddenElement.target = '_blank';
        hiddenElement.download = violation.image;
        hiddenElement.href = `data:image/jpeg;base64,${readFile.data}`;
        hiddenElement.click();
      });
    });
  }
}
