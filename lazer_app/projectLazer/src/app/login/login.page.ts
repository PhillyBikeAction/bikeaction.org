import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { NgForm } from '@angular/forms';

import { OnlineStatusService } from '../services/online.service';
import { UpdateService } from '../services/update.service';
import { AccountService } from '../services/account.service';

interface UserOptions {
  username: string;
  password: string;
}

@Component({
  selector: 'app-login',
  templateUrl: './login.page.html',
  styleUrls: ['./login.page.scss'],
  standalone: false,
})
export class LoginPage implements OnInit {
  login: UserOptions = { username: '', password: '' };
  submitted: boolean = false;
  next: any = null;

  constructor(
    public accountService: AccountService,
    public onlineStatus: OnlineStatusService,
    public updateService: UpdateService,
    private router: Router,
    private route: ActivatedRoute,
  ) {}

  async onLogin(form: NgForm) {
    this.submitted = true;

    if (form.valid) {
      await this.accountService.logIn(this.login.username, this.login.password);

      if (this.accountService.loggedIn === true) {
        if (this.next) {
          this.router.navigateByUrl(this.next);
        } else {
          this.router.navigate(['home']);
        }
      }
    }
  }

  ngOnInit() {
    this.next = this.route.snapshot.queryParams['next'];
  }
}
