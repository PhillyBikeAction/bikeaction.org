import { Capacitor } from '@capacitor/core';
import { Camera, CameraResultType, CameraSource } from '@capacitor/camera';
import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { LoadingController, ToastController } from '@ionic/angular';
import { Platform } from '@ionic/angular'; // Import Platform

import { Device, DeviceInfo } from '@capacitor/device';
import { Geolocation, Position } from '@capacitor/geolocation';
import { Storage } from '@ionic/storage-angular';

import { v4 as uuidv4 } from 'uuid';

import { fromURL, blobToURL } from 'image-resize-compress';

import { OnlineStatusService } from '../services/online.service';
import { PhotoService } from '../services/photo.service';
import { UpdateService } from '../services/update.service';
import { ViolationService } from '../services/violation.service';

@Component({
  selector: 'app-home',
  templateUrl: 'home.page.html',
  styleUrls: ['home.page.scss'],
  standalone: false,
})
export class HomePage implements OnInit {
  deviceInfo: DeviceInfo | null = null;

  geoPerms: boolean | null = null;
  geoWatchId: string | null = null;

  violationId: number | null = null;
  violationImage: string | undefined | null = null;
  violationPosition: Position | null = null;
  violationTime: Date | null = null;

  constructor(
    private loadingCtrl: LoadingController,
    private toastController: ToastController,
    private router: Router,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
    private photos: PhotoService,
    private storage: Storage,
    private violations: ViolationService,
    public platform: Platform,
  ) {}

  async getCurrentPosition() {
    if (this.geoWatchId !== null) {
      Geolocation.clearWatch({ id: this.geoWatchId });
    }
    this.geoWatchId = await Geolocation.watchPosition(
      { enableHighAccuracy: true, maximumAge: 10000 },
      (coordinates) => {
        if (coordinates!.coords!.accuracy < 50) {
          this.violationPosition = coordinates;
          this.geoPerms = true;
          if (this.geoWatchId !== null) {
            Geolocation.clearWatch({ id: this.geoWatchId });
          }
        }
      },
    );
    //this.violationPosition = {
    //  timestamp: 123,
    //  coords: {
    //    latitude: 39.9526,
    //    longitude: 75.1652,
    //    accuracy: 10,
    //    speed: null,
    //    heading: null,
    //    altitude: null,
    //    altitudeAccuracy: null,
    //  },
    //};
  }

  async takePicture() {
    this.violationImage = null;
    this.violationPosition = null;
    this.violationTime = null;
    this.getCurrentPosition();

    const image = await Camera.getPhoto({
      quality: 60,
      resultType: CameraResultType.Base64,
      source: CameraSource.Camera,
      webUseInput: true,
      saveToGallery: true,
    });

    const imageId = uuidv4();
    console.log(imageId);
    const savedImage = await this.photos.savePictureFromBase64(
      image.base64String as string,
      `${imageId}.jpg`,
    );
    fromURL(savedImage.webviewPath as string, 0.5, 480, 'auto', 'jpeg').then(
      (thumbnail) => {
        blobToURL(thumbnail).then((thumbnailUrl) => {
          const savedThumbnail = this.photos.savePictureFromBase64(
            thumbnailUrl as string,
            `thumb-${imageId}.jpg`,
          );
        });
      },
    );
    this.violationImage = savedImage.webviewPath;
    this.violationTime = new Date();
    this.violationId = await this.storage.get('violationId').then((value) => {
      let violationId;
      if (value !== null) {
        violationId = value;
      } else {
        violationId = 1;
      }
      this.storage.set('violationId', violationId! + 1);
      return violationId;
    });
    this.storage
      .set('violation-' + this.violationId, {
        id: this.violationId,
        image: JSON.parse(JSON.stringify(savedImage.filepath)),
        thumbnail: JSON.parse(JSON.stringify(`thumb-${savedImage.filepath}`)),
        time: JSON.parse(JSON.stringify(this.violationTime)),
        position: JSON.parse(JSON.stringify(this.violationPosition)),
        processed: false,
        submitted: false,
        violationType: null,
        vehicle: null,
        address: null,
        raw: null,
      })
      .then((data) => {
        this.loadingCtrl
          .create({
            message: 'Waiting for geolocation data...',
          })
          .then((loader) => {
            loader.present().then(() => {
              let locationTimeoutID = setTimeout(async () => {
                await loader.dismiss();
                const toast = await this.toastController.create({
                  message: 'Unable to geolocate your photo, try again',
                  duration: 2000,
                  position: 'top',
                  icon: 'alert-circle-outline',
                });
                await toast.present();

                this.violationImage = null;
              }, 10000);
              let check = function (dis: any) {
                setTimeout(function () {
                  if (dis.violationPosition !== null) {
                    const violationData = dis.storage
                      .get('violation-' + dis.violationId)
                      .then((data: any) => {
                        data.position = JSON.parse(
                          JSON.stringify(dis.violationPosition),
                        );
                        dis.storage
                          .set('violation-' + dis.violationId, data)
                          .then((data: any) => {
                            clearTimeout(locationTimeoutID);
                            loader.dismiss();
                            dis.violationImage = null;
                            dis.violationPosition = null;
                            dis.router.navigate(['/violation-detail'], {
                              queryParams: { violationId: data.id },
                            });
                          });
                      });
                  } else {
                    check(dis);
                  }
                }, 100);
              };
              check(this);
            });
          });
      });
  }

  requestGeoPerms = () => {
    if (Capacitor.isNativePlatform()) {
      Geolocation.requestPermissions();
    } else {
      this.getCurrentPosition();
    }
    this.checkPermission();
  };

  checkPermission = async () => {
    if (Capacitor.isNativePlatform()) {
      try {
        const status = await Geolocation.checkPermissions();
        if (status.location == 'granted') {
          this.geoPerms = true;
        }
      } catch (e) {
        console.log(e);
        this.geoPerms = false;
      }
    } else {
      navigator.permissions.query({ name: 'geolocation' }).then((result) => {
        if (result.state === 'granted') {
          this.geoPerms = true;
        } else if (result.state === 'prompt') {
          if (
            this.deviceInfo !== null &&
            this.deviceInfo.operatingSystem === 'ios'
          ) {
            this.geoPerms = true;
          } else {
            this.geoPerms = false;
          }
        } else {
          this.geoPerms = false;
        }
      });
    }
  };

  ionViewDidEnter() {
    this.violations.cleanup();
  }

  ngOnInit(): void {
    Device.getInfo().then((deviceInfo) => {
      this.deviceInfo = deviceInfo;
      this.checkPermission();
    });
  }
}
