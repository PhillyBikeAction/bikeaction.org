import { TestBed } from '@angular/core/testing';
import { Router } from '@angular/router';
import {
  AlertController,
  LoadingController,
  ModalController,
  Platform,
  ToastController,
} from '@ionic/angular';
import { Storage } from '@ionic/storage-angular';
import { AddressParser } from '@sroussey/parse-address';

import { AccountService } from '../services/account.service';
import { OnlineStatusService } from '../services/online.service';
import { PhotoService } from '../services/photo.service';
import { ConfirmViolationDetailsModalComponent } from './confirm-violation-details-modal.component';

describe('ConfirmViolationDetailsModalComponent address initialization', () => {
  let component: ConfirmViolationDetailsModalComponent;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ...[
          AlertController,
          LoadingController,
          ModalController,
          ToastController,
          Router,
          Storage,
          AccountService,
          OnlineStatusService,
          PhotoService,
        ].map((provide) => ({ provide, useValue: {} })),
        { provide: Platform, useValue: { is: () => false } },
      ],
    });
    component = TestBed.runInInjectionContext(
      () => new ConfirmViolationDetailsModalComponent(),
    );
    component.violation = { address: '123 N Main St, Philadelphia, PA 19103', vehicle: {} };
  });

  it('prefills the editable fields from a recognized address', () => {
    component.ngOnInit();

    expect(component.blockNumber).toBe('123');
    expect(component.streetName).toBe('N MAIN ST');
    expect(component.zipCode).toBe('19103');
  });

  it('leaves the editable fields blank when the parser cannot recognize an address', () => {
    spyOn(AddressParser.prototype, 'parseLocation').and.returnValue(null);

    expect(() => component.ngOnInit()).not.toThrow();
    expect(component.blockNumber).toBe('');
    expect(component.streetName).toBe('');
    expect(component.zipCode).toBe('');
  });
});
