import { Component } from '@angular/core';

import { OnlineStatusService } from '../services/online.service';
import { UpdateService } from '../services/update.service';
import { AccountService } from '../services/account.service';

@Component({
  selector: 'app-about',
  templateUrl: './about.page.html',
  styleUrls: ['./about.page.scss'],
  standalone: false,
})
export class AboutPage {
  constructor(
    public accountService: AccountService,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
  ) {}
}
