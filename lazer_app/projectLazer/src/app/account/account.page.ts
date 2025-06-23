import { Component } from '@angular/core';

import { OnlineStatusService } from '../services/online.service';
import { UpdateService } from '../services/update.service';
import { AccountService } from '../services/account.service';

@Component({
  selector: 'app-account',
  templateUrl: './account.page.html',
  styleUrls: ['./account.page.scss'],
  standalone: false,
})
export class AccountPage {
  constructor(
    public accountService: AccountService,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
  ) {}
}
