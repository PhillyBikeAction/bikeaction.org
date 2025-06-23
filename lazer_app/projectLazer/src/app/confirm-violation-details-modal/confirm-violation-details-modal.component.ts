import { Component, Input, OnInit, ViewChild } from '@angular/core';
import {
  AlertController,
  LoadingController,
  ModalController,
  ToastController,
} from '@ionic/angular';

import { Router } from '@angular/router';
import { Platform } from '@ionic/angular';

import { Browser } from '@capacitor/browser';
import { Storage } from '@ionic/storage-angular';
import { IonModal } from '@ionic/angular';

import { parseAddress } from 'vladdress';
import { usaStates } from 'typed-usa-states/dist/states';
import { fromURL, blobToURL } from 'image-resize-compress';

import { RenderImagePipe } from '../render-image.pipe';
import { PhotoService } from '../services/photo.service';
import { SuccessModalComponent } from '../success-modal/success-modal.component';

import { OnlineStatusService } from '../services/online.service';
import { AccountService } from '../services/account.service';

import { Item } from '../components/types';

import {
  best_match,
  get_options,
} from '../violation-matcher/violation-matcher';

function mapToUrlParams(map: any) {
  const params = new URLSearchParams();
  for (const key in map) {
    if (map.hasOwnProperty(key)) {
      params.append(key, map[key]);
    }
  }
  return params.toString();
}

@Component({
  selector: 'app-confirm-violation-details-modal',
  templateUrl: './confirm-violation-details-modal.component.html',
  styleUrls: ['./confirm-violation-details-modal.component.scss'],
  standalone: false,
})
export class ConfirmViolationDetailsModalComponent implements OnInit {
  @ViewChild('streetNameModal', { static: true }) streetNameModal!: IonModal;
  @ViewChild('zipCodeModal', { static: true }) zipCodeModal!: IonModal;

  rootUrl: string = '';

  make!: string;
  model!: string;
  bodyStyle!: string;
  vehicleColor!: string;

  frequency: string = 'Unsure';

  blockNumber!: string;
  streetName!: string;
  zipCode!: string;

  plateState!: string;
  plateNumber!: string;

  fields: string[] = [
    'Body Style',
    'Make',
    'Vehicle Color',

    'Block Number',
    'Street Name',
    'Zip Code',

    'How frequently does this occur?',
  ];

  streetNameOptions: any = this.getOptions('Street Name').map((elem) => {
    return new Map([
      ['value', elem],
      ['text', elem],
    ]);
  });
  streetNameChanged(streetName: string) {
    this.streetName = streetName;
    this.streetNameModal.dismiss();
  }

  zipCodeOptions: any = this.getOptions('Zip Code').map((elem) => {
    return new Map([
      ['value', elem],
      ['text', elem],
    ]);
  });
  zipCodeChanged(zipCode: string) {
    this.zipCode = zipCode;
    this.zipCodeModal.dismiss();
  }

  @Input() violation: any;
  @Input() form: any;

  constructor(
    private alertController: AlertController,
    private modalCtrl: ModalController,
    private loadingCtrl: LoadingController,
    private toastController: ToastController,
    private router: Router,
    private photos: PhotoService,
    private storage: Storage,
    public onlineStatus: OnlineStatusService,
    private accountService: AccountService,
    private platform: Platform,
  ) {}

  async presentReallySubmit() {
    const alert = await this.alertController.create({
      header: 'Are you sure?',
      subHeader:
        'This will really make a report to the PPA. Make sure all details are correct before submitting!',
      buttons: [
        {
          text: 'Cancel',
          role: 'cancel',
          handler: () => {
            this.cancel();
          },
        },
        {
          text: 'Submit it!',
          role: 'confirm',
          handler: () => {
            this.submit();
          },
        },
      ],
    });
    await alert.present();
  }

  cancel() {
    return this.modalCtrl.dismiss(null, 'cancel');
  }

  submit() {
    const submitUrl = `${this.rootUrl}/lazer/api/report/`;
    function submitData(
      submission_id: string,
      date_observed: string,
      time_observed: string,
      make: string,
      model: string,
      body_style: string,
      vehicle_color: string,
      violation_observed: string,
      occurrence_frequency: string,
      block_number: string,
      street_name: string,
      zip_code: string,
      additional_information: string,
      img: string,
      headers: any,
    ): Promise<any> {
      return new Promise((resolve, reject) => {
        fromURL(img, 0.3, 'auto', 'auto', 'jpeg').then((resizedBlob) => {
          blobToURL(resizedBlob).then((imgUrl) => {
            const formData = new FormData();
            let uuid = submission_id ? submission_id : crypto.randomUUID();

            formData.append('submission_id', uuid);
            formData.append('date_observed', date_observed);
            formData.append('time_observed', time_observed);
            formData.append('make', make);
            formData.append('model', model);
            formData.append('body_style', body_style);
            formData.append('vehicle_color', vehicle_color);
            formData.append('violation_observed', violation_observed);
            formData.append('occurrence_frequency', occurrence_frequency);
            formData.append('block_number', block_number);
            formData.append('street_name', street_name);
            formData.append('zip_code', zip_code);
            formData.append('additional_information', additional_information);
            formData.append('image', imgUrl as string);

            try {
              fetch(submitUrl, {
                method: 'POST',
                body: formData,
                headers: headers,
              }).then((response) => {
                if (!response.ok) {
                  if (response.status === 400) {
                    response.json().then((json) => {
                      reject(json.error);
                    });
                  }
                  throw new Error(`Response status: ${response.status}`);
                }
                response.json().then((json) => {
                  resolve(json);
                });
              });
            } catch (error: any) {
              reject('error reporting, try again?');
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
        this.photos.fetchPicture(this.violation.image!).then((photo) => {
          const violationTime = new Date(this.violation.time!);
          let additionalInfo = 'none at this time';
          if (this.plateNumber || this.plateState) {
            additionalInfo = `Plate: ${this.plateState!} ${this.plateNumber}`;
          }

          submitData(
            this.violation.submissionId,
            violationTime.toLocaleDateString('en-US', {
              month: '2-digit',
              day: '2-digit',
              year: 'numeric',
            }),
            violationTime.toLocaleTimeString('en-US'),
            this.make,
            this.model,
            this.bodyStyle,
            this.vehicleColor,
            this.violation.violationType,
            this.frequency,
            this.blockNumber,
            this.streetName,
            this.zipCode,
            additionalInfo,
            photo.webviewPath,
            this.accountService.headers(),
          )
            .then((data: any) => {
              this.violation.submitted = true;
              this.storage
                .set('violation-' + this.violation.id, this.violation)
                .then((data) => {
                  setTimeout(async () => {
                    this.success();
                    this.cancel();
                    loader.dismiss();
                    this.router.navigate(['home']);
                  }, 100);
                });
            })
            .catch((err: any) => {
              console.log(err);
              setTimeout(async () => {
                const toast = await this.toastController.create({
                  message: `Error: ${err}`,
                  duration: 2000,
                  position: 'top',
                  icon: 'alert-circle-outline',
                });
                await toast.present();
                loader.dismiss();
              }, 100);
            });
        });
      });
  }

  async success() {
    const successModal = await this.modalCtrl.create({
      component: SuccessModalComponent,
    });
    successModal.present();
    setTimeout(async () => {
      await successModal.dismiss();
    }, 1500);
  }

  submitBrowser() {
    const imageBase64 = this.photos.readAsBase64(this.violation.image);
    const violationTime = new Date(this.violation.time!);
    let additionalInfo = 'none at this time';
    if (this.plateNumber || this.plateState) {
      additionalInfo = `Plate: ${this.plateState!} ${this.plateNumber}`;
    }
    const params = {
      'Date Observed': violationTime.toLocaleDateString('en-US', {
        month: '2-digit',
        day: '2-digit',
        year: 'numeric',
      }),
      'Time Observed': violationTime.toLocaleTimeString('en-US'),
      Make: this.make,
      Model: this.model,
      'Body Style': this.bodyStyle,
      'Vehicle Color': this.vehicleColor,
      'Violation Observed': this.violation.violationType,
      'How frequently does this occur?': this.frequency,
      'Block Number': this.blockNumber,
      'Street Name': this.streetName,
      'Zip Code': this.zipCode,
      'Additional Information': additionalInfo,
    };
    const submissionUrl =
      'https://app.smartsheet.com/b/form/463e9faa2a644f4fae2a956f331f451c?' +
      mapToUrlParams(params);
    console.log(submissionUrl);
    Browser.open({ url: submissionUrl });
  }

  confirm() {
    this.modalCtrl.dismiss(this.form, 'save');
  }
  getOptions(field: string): string[] {
    return get_options(field) as string[];
  }
  getStates(): Map<string, string> {
    return new Map(
      usaStates.map(
        (obj) => [obj.abbreviation as string, obj.name as string] as const,
      ),
    );
  }

  ngOnInit(): void {
    if (this.platform.is('hybrid')) {
      this.rootUrl = 'https://bikeaction.org';
    }
    const parsedAddress = parseAddress(this.violation.address);
    this.blockNumber = parsedAddress.streetNumber as string;
    this.streetName = best_match(
      'Street Name',
      `${parsedAddress.streetName} ${parsedAddress.streetSuffix}`,
    );
    this.zipCode = best_match('Zip Code', parsedAddress.zipCode as string);

    if (this.violation.vehicle!.vehicle?.props?.make_model[0].make) {
      this.make = best_match(
        'Make',
        this.violation.vehicle.vehicle.props.make_model[0].make,
      );
    }
    if (this.violation.vehicle!.vehicle?.props?.make_model[0].model) {
      this.model = this.violation.vehicle.vehicle.props.make_model[0].model;
    }
    if (this.violation.vehicle!.vehicle?.props?.color[0].value) {
      this.vehicleColor = best_match(
        'Vehicle Color',
        this.violation.vehicle.vehicle.props.color[0].value,
      );
    }
    if (this.violation.vehicle!.vehicle?.type) {
      this.bodyStyle = best_match(
        'Body Style',
        this.violation.vehicle.vehicle.type,
      );
    }
    if (this.violation.vehicle!.plate) {
      this.plateNumber =
        this.violation.vehicle.plate.props.plate[0].value.toUpperCase();
      this.plateState = this.violation.vehicle.plate.props.region[0].value
        .replace('us-', '')
        .toUpperCase();
    }
    console.log(this.plateNumber, this.plateState);
    console.log(this.blockNumber, this.streetName, this.zipCode);
    console.log(this.make, this.model, this.vehicleColor, this.bodyStyle);
  }
}
