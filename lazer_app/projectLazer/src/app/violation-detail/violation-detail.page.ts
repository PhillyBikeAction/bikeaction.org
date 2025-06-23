import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Storage } from '@ionic/storage-angular';
import { Platform } from '@ionic/angular';

import { LoadingController, ModalController } from '@ionic/angular';

import { fromURL, blobToURL } from 'image-resize-compress';

import { OnlineStatusService } from '../services/online.service';
import { PhotoService, UserPhoto } from '../services/photo.service';
import { UpdateService } from '../services/update.service';
import { AccountService } from '../services/account.service';

import { ChooseAddressModalComponent } from '../choose-address-modal/choose-address-modal.component';
import { ChooseViolationModalComponent } from '../choose-violation-modal/choose-violation-modal.component';
import { ConfirmViolationDetailsModalComponent } from '../confirm-violation-details-modal/confirm-violation-details-modal.component';
import { best_match } from '../violation-matcher/violation-matcher';

@Component({
  selector: 'app-violation-detail',
  templateUrl: './violation-detail.page.html',
  styleUrls: ['./violation-detail.page.scss'],
  standalone: false,
})
export class ViolationDetailPage implements OnInit {
  violationId: number | null = null;
  violationData: any = null;
  violationImageLoaded: boolean = false;
  location: string | null = null;
  rootUrl: string = '';

  constructor(
    public route: ActivatedRoute,
    private loadingCtrl: LoadingController,
    public changeDetectorRef: ChangeDetectorRef,
    private modalCtrl: ModalController,
    private storage: Storage,
    public photos: PhotoService,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
    public accountService: AccountService,
    private platform: Platform,
  ) {}

  async selectVehicle(index: number) {
    this.violationData.vehicle = this.violationData.raw.vehicles[index];
    this.storage.set('violation-' + this.violationId, this.violationData);
    this.drawHitBoxes();
    this.changeDetectorRef.detectChanges();
  }

  async drawHitBoxes() {
    if (!this.violationData.raw?.vehicles) {
      return;
    }
    const image = document.getElementById('imagePreview') as HTMLImageElement;
    const shadowRoot = image.shadowRoot;
    const shadowImage = shadowRoot!.querySelector('img');
    const rect = shadowImage!.getBoundingClientRect();

    shadowRoot!.getElementById('imageOverlay')?.remove();

    const overlayDiv = document.createElement('div');
    overlayDiv.id = 'imageOverlay';
    overlayDiv.className = 'imageOverlay';
    overlayDiv.style.position = 'absolute';
    overlayDiv.style.width = rect.width + 'px';
    overlayDiv.style.height = rect.height + 'px';
    shadowImage!.insertAdjacentElement('beforebegin', overlayDiv);

    const scale =
      (shadowImage!.width / shadowImage!.naturalWidth +
        shadowImage!.height / shadowImage!.naturalHeight) /
      2;

    this.violationData.raw.vehicles.forEach((element: any, index: number) => {
      if (element.vehicle) {
        const box = document.createElement('a');
        box.style.position = 'absolute';
        box.style.zIndex = `${15 - index}`;
        if (
          JSON.stringify(element) === JSON.stringify(this.violationData.vehicle)
        ) {
          box.style.border = '3px solid hotpink';
        } else {
          box.style.border = '3px solid lime';
        }
        box.style.left = element.vehicle.box.xmin * scale + 'px';
        box.style.top = element.vehicle.box.ymin * scale + 'px';
        box.addEventListener('click', (event) => {
          this.selectVehicle(index);
        });
        box.style.width =
          (element.vehicle.box.xmax - element.vehicle.box.xmin) * scale + 'px';
        box.style.height =
          (element.vehicle.box.ymax - element.vehicle.box.ymin) * scale + 'px';
        overlayDiv.appendChild(box);
      }
      if (element.plate) {
        const box = document.createElement('div');
        box.style.position = 'absolute';
        box.style.zIndex = '8';
        box.style.border = '2px solid yellow';
        box.style.left =
          (element.plate.box.xmin / shadowImage!.naturalWidth) *
            shadowImage!.width +
          'px';
        box.style.top =
          (element.plate.box.ymin / shadowImage!.naturalHeight) *
            shadowImage!.height +
          'px';
        box.style.width =
          ((element.plate.box.xmax - element.plate.box.xmin) /
            shadowImage!.naturalWidth) *
            shadowImage!.width +
          'px';
        box.style.height =
          ((element.plate.box.ymax - element.plate.box.ymin) /
            shadowImage!.naturalHeight) *
            shadowImage!.height +
          'px';
        overlayDiv.appendChild(box);
      }
    });
  }

  async reprocess() {
    this.violationData.processed = false;
    this.violationData.raw = null;
    this.violationData.address = null;
    this.violationData.addressCandidates = null;
    this.violationData.vehicle = null;
    this.violationData.violationType = null;
    this.submit();
  }

  async submit() {
    const submitUrl = `${this.rootUrl}/lazer/api/submit/`;
    function submitData(
      lat: number,
      long: number,
      dt: Date,
      img: string,
      headers: any,
    ): Promise<any> {
      return new Promise((resolve, reject) => {
        fromURL(img, 0.3, 'auto', 'auto', 'jpeg').then((resizedBlob) => {
          blobToURL(resizedBlob).then((imgUrl) => {
            const formData = new FormData();
            formData.append('latitude', JSON.stringify(lat));
            formData.append('longitude', JSON.stringify(long));
            formData.append('datetime', dt.toISOString());
            formData.append('image', imgUrl as string);

            try {
              fetch(submitUrl, {
                method: 'POST',
                body: formData,
                headers: headers,
              }).then((response) => {
                if (!response.ok) {
                  throw new Error(`Response status: ${response.status}`);
                }
                response.json().then((json) => {
                  resolve(json);
                });
              });
            } catch (error: any) {
              reject('error processing, try again?');
            }
          });
        });
      });
    }

    this.loadingCtrl
      .create({
        message: 'Processing...',
        duration: 20000,
      })
      .then((loader) => {
        loader.present();
        const violationTime = new Date(this.violationData.time!);
        this.photos.fetchPicture(this.violationData.image!).then((photo) => {
          submitData(
            this.violationData.position!.coords!.latitude,
            this.violationData.position!.coords!.longitude,
            violationTime,
            photo.webviewPath,
            this.accountService.headers(),
          )
            .then((data: any) => {
              this.violationData.raw = data;
              this.storage.set(
                'violation-' + this.violationId,
                this.violationData,
              );
              if (data.vehicles.length == 1) {
                this.selectVehicle(0);
              }
              this.violationData.processed = true;
              this.violationData.address = data.address;
              this.violationData.addressCandidates = data.addresses;
              this.violationData.submissionId = data.submissionId;
              this.storage
                .set('violation-' + this.violationId, this.violationData)
                .then((data) => {
                  setTimeout(() => {
                    this.changeDetectorRef.detectChanges();
                    loader.dismiss();
                    this.drawHitBoxes();
                  }, 100);
                });
            })
            .catch((err: any) => {
              console.log(err);
              setTimeout(() => {
                loader.dismiss();
              }, 100);
            });
        });
      });
  }

  async openModal() {
    const chooseViolationModal = await this.modalCtrl.create({
      component: ChooseViolationModalComponent,
    });
    chooseViolationModal.present();

    const { data, role } = await chooseViolationModal.onWillDismiss();

    if (role === 'save') {
      this.violationData.violationType = data;
      this.storage
        .set('violation-' + this.violationId, this.violationData)
        .then((data) => {
          this.changeDetectorRef.detectChanges();
        });
    } else {
      return;
    }

    this.openViolationModal();
  }

  async openAddressModal() {
    if (this.violationData.addressCandidates) {
      const chooseAddressModal = await this.modalCtrl.create({
        component: ChooseAddressModalComponent,
        componentProps: { violation: this.violationData },
      });
      chooseAddressModal.present();

      const { data, role } = await chooseAddressModal.onWillDismiss();

      if (role === 'save') {
        this.violationData.address = data;
        this.storage
          .set('violation-' + this.violationId, this.violationData)
          .then((data) => {
            this.changeDetectorRef.detectChanges();
          });
      } else {
        return;
      }
    }

    this.openModal();
  }

  async openViolationModal() {
    const confirmViolationDetailsModal = await this.modalCtrl.create({
      component: ConfirmViolationDetailsModalComponent,
      componentProps: { violation: this.violationData },
    });
    confirmViolationDetailsModal.present();
    const { data, role } = await confirmViolationDetailsModal.onWillDismiss();

    if (role === 'save') {
    } else {
      return;
    }
  }

  ngOnInit() {
    if (this.platform.is('hybrid')) {
      this.rootUrl = 'https://bikeaction.org';
    }
    this.location = window.location.pathname + window.location.search;
    this.violationId = this.route.snapshot.queryParams['violationId'];
    this.storage.get('violation-' + this.violationId).then((data) => {
      this.violationData = data;
    });
  }
}
