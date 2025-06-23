import { Component, OnInit } from '@angular/core';
import { Storage } from '@ionic/storage-angular';
import { Platform } from '@ionic/angular'; // Import Platform

import { OnlineStatusService } from './services/online.service';
import { UpdateService } from './services/update.service';
import { VersionService } from './services/version.service';
import { AccountService } from './services/account.service';

@Component({
  selector: 'app-root',
  templateUrl: 'app.component.html',
  styleUrls: ['app.component.scss'],
  standalone: false,
})
export class AppComponent implements OnInit {
  private xDown: number | null = null;
  private yDown: number | null = null;

  handleTouchStart(e: any) {
    this.xDown = e.touches[0].clientX;
    this.yDown = e.touches[0].clientY;
  }
  handleTouchMove(e: any) {
    if (!this.xDown || !this.yDown) {
      return;
    }

    let xUp = e.touches[0].clientX;
    let yUp = e.touches[0].clientY;

    let xDiff = this.xDown - xUp;
    let yDiff = this.yDown - yUp;

    if (Math.abs(xDiff) > Math.abs(yDiff)) {
      if (xDiff > 0) {
        /* left swipe */
        e.preventDefault();
      } else {
        /* right swipe */
        e.preventDefault();
      }
    }
  }

  ngOnInit(): void {
    this.accountService.checkLoggedIn();
    if (this.platform.is('hybrid')) {
      this.platform.resume.subscribe(() => {
        this.accountService.checkLoggedIn();
        this.updateService.checkForUpdateNow();
      });
    } else {
      document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
        } else {
          this.accountService.checkLoggedIn();
          this.updateService.checkForUpdateNow();
        }
      });
    }
  }

  constructor(
    private platform: Platform,
    private storage: Storage,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
    public versionService: VersionService,
    public accountService: AccountService,
  ) {
    this.storage.create();
    document.addEventListener('touchstart', this.handleTouchStart, {
      passive: false,
    });
    document.addEventListener('touchmove', this.handleTouchMove, {
      passive: false,
    });
  }
}
