import { Injectable, NgZone, OnDestroy } from '@angular/core';
import { SwUpdate } from '@angular/service-worker';
import { Subscription, interval } from 'rxjs';
import { LocationStrategy } from '@angular/common';

@Injectable({
  providedIn: 'root',
})
export class UpdateService implements OnDestroy {
  needsUpdate: boolean = false;
  isNewVersionAvailable: boolean = false;
  intervalSource = interval(15 * 60 * 1000); // every 15 mins
  intervalSubscription?: Subscription;

  constructor(
    private swUpdate: SwUpdate,
    private zone: NgZone,
    private locationStrategy: LocationStrategy,
  ) {
    this.checkForUpdate();
  }

  async checkForUpdateNow(): Promise<void> {
    this.intervalSubscription?.unsubscribe();

    try {
      this.isNewVersionAvailable = await this.swUpdate.checkForUpdate();
      this.needsUpdate = this.isNewVersionAvailable || this.needsUpdate;
      console.log(
        this.isNewVersionAvailable
          ? 'A new version is available.'
          : 'Already on the latest version.',
      );
    } catch (error) {
      console.error('Failed to check for updates:', error);
    }

    this.checkForUpdate();
  }

  checkForUpdate(): void {
    this.intervalSubscription?.unsubscribe();

    this.zone.runOutsideAngular(() => {
      this.intervalSubscription = this.intervalSource.subscribe(async () => {
        this.checkForUpdateNow();
      });
    });
  }

  applyUpdate(): void {
    this.needsUpdate = false;
    // Reload the page to update to the latest version after the new version is activated
    this.swUpdate
      .activateUpdate()
      .then(
        () => (document.location.href = this.locationStrategy.getBaseHref()),
      )
      .catch((error) => console.error('Failed to apply updates:', error));
  }

  ngOnDestroy(): void {
    this.intervalSubscription?.unsubscribe();
  }
}
