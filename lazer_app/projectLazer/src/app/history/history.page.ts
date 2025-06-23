import { Component, ChangeDetectorRef } from '@angular/core';

import { Directory, Filesystem } from '@capacitor/filesystem';
import { Storage } from '@ionic/storage-angular';

import { OnlineStatusService } from '../services/online.service';
import { PhotoService, UserPhoto } from '../services/photo.service';
import { UpdateService } from '../services/update.service';
import { ViolationService } from '../services/violation.service';

@Component({
  selector: 'app-history',
  templateUrl: './history.page.html',
  styleUrls: ['./history.page.scss'],
  standalone: false,
})
export class HistoryPage {
  violationHistory: any[] = [];

  constructor(
    public onlineStatus: OnlineStatusService,
    private storage: Storage,
    private violations: ViolationService,
    public photos: PhotoService,
    public changeDetectorRef: ChangeDetectorRef,
    public updateService: UpdateService,
  ) {}

  async renderPhoto(filename: string): Promise<UserPhoto> {
    return await this.photos.fetchPicture(filename);
  }

  trackViolations(index: number, violation: any) {
    return violation.id;
  }

  getThumb(violation: any) {
    if (violation.thumbnail) {
      return violation.thumbnail;
    }
    return violation.image;
  }

  deleteViolation(violationId: number) {
    this.violations.deleteViolation(violationId);
    this.violationHistory = this.violationHistory.filter(
      (item) => item.id !== violationId,
    );
    this.changeDetectorRef.detectChanges();
  }

  actionButtons(violationId: number) {
    return [
      {
        text: 'Cancel',
        role: 'cancel',
        handler: () => {},
      },
      {
        text: 'OK',
        role: 'confirm',
        handler: () => {
          this.deleteViolation(violationId);
        },
      },
    ];
  }

  async saveImage(violationId: number) {
    this.violations.saveImage(violationId);
  }

  sortViolations() {
    return this.violationHistory
      .sort(function (a, b) {
        var x = new Date(a.time);
        var y = new Date(b.time);
        return x > y ? -1 : x < y ? 1 : 0;
      })
      .slice(0, 20);
  }

  ionViewWillEnter() {
    this.violations.cleanup();
    this.violations.history().then((history) => {
      this.violationHistory = history;
    });
  }
}
