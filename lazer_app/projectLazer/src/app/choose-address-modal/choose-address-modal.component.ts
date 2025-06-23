import { Component, Input, OnInit } from '@angular/core';
import { ModalController } from '@ionic/angular';

@Component({
  selector: 'app-choose-address-modal',
  templateUrl: './choose-address-modal.component.html',
  styleUrls: ['./choose-address-modal.component.scss'],
  standalone: false,
})
export class ChooseAddressModalComponent implements OnInit {
  selection!: string;
  addresses!: string[];

  @Input() violation: any;

  constructor(private modalCtrl: ModalController) {}

  setAddress(address: string) {
    this.selection = address;
    this.modalCtrl.dismiss(this.selection, 'save');
  }

  cancel() {
    return this.modalCtrl.dismiss({ note: null }, 'cancel');
  }

  confirm() {
    this.modalCtrl.dismiss(this.selection, 'save');
  }

  ngOnInit(): void {
    this.addresses = this.violation.addressCandidates.filter(
      (address: string) =>
        (address as string).split(',').length >= 4 &&
        address.match(/^\d/) &&
        !(address as string).split(',')[0].includes(' & '),
    );
  }
}
