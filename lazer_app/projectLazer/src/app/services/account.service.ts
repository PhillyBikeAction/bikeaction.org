import { Injectable } from '@angular/core';
import { Platform } from '@ionic/angular';
import { Storage } from '@ionic/storage-angular';
import { ToastController } from '@ionic/angular';
import { Preferences } from '@capacitor/preferences';

@Injectable({
  providedIn: 'root',
})
export class AccountService {
  username: string | null = null;
  loggedIn: boolean = false;
  urlRoot: string = '';
  session_key: string | null = null;
  expiry_date: string | null = null;

  headers() {
    const headers = new Headers();
    headers.append('Authorization', `Session: ${this.session_key}`);
    return headers;
  }

  async checkLoggedIn() {
    await this.loadSession();
    const url = `${this.urlRoot}/lazer/api/check-login/`;
    try {
      const response = await fetch(url, {
        method: 'GET',
        redirect: 'error',
        headers: this.headers(),
      });
      if (!response.ok) {
        if (response.status === 403) {
          await this.storage.set('loggedIn', null);
          this.loggedIn = false;
          await this.storage.set('loggedIn', null);
          this.session_key = null;
          await Preferences.remove({ key: 'session_key' });
          return;
        } else {
          throw new Error(`Response status: ${response.status}`);
        }
      }

      const json = await response.json();
      this.username = json.username;
      this.loggedIn = true;
      await this.storage.set('loggedIn', this.username);
    } catch (error: any) {
      if (error.message) {
        await this.presentError(error.message);
      }
    }
  }

  async logIn(username: string, password: string) {
    const url = `${this.urlRoot}/lazer/api/login/`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        body: JSON.stringify({ username: username, password: password }),
        redirect: 'error',
      });
      if (!response.ok) {
        throw new Error(`Response status: ${response.status}`);
      }

      const json = await response.json();
      this.username = json.username;
      this.session_key = json.session_key;
      this.expiry_date = json.expiry_date;
      this.loggedIn = true;
      await this.storage.set('loggedIn', this.username);
      await Preferences.set({
        key: 'session_key',
        value: this.session_key as string,
      });
      await this.presentSuccess(json);
    } catch (error: any) {
      console.log(error);
      if (error.message) {
        await this.presentError(error.message);
      }
    }
  }

  async logOut() {
    const url = `${this.urlRoot}/lazer/api/logout/`;
    try {
      const response = await fetch(url, {
        redirect: 'error',
        headers: this.headers(),
      });
      if (!response.ok) {
        throw new Error(`Response status: ${response.status}`);
      }

      const json = await response.json();
      this.username = null;
      this.loggedIn = false;
      await this.storage.set('loggedIn', null);
      this.session_key = null;
      await Preferences.remove({ key: 'session_key' });
    } catch (error: any) {
      console.log(error.message);
    }
  }

  async presentError(message: string) {
    const toast = await this.toastController.create({
      message: 'Invalid Auth: ' + message,
      duration: 1000,
      position: 'top',
      icon: 'alert',
    });
    toast.present();
  }

  async presentSuccess(data: any) {
    const toast = await this.toastController.create({
      message: 'Success! Welcome, ' + data.username,
      duration: 1000,
      position: 'top',
      icon: 'check',
    });
    toast.present();
  }

  async loadSession() {
    await Preferences.get({ key: 'session_key' }).then((value) => {
      this.session_key = value.value;
    });
    await this.storage.get('loggedIn').then((username) => {
      if (username) {
        this.loggedIn = true;
        this.username = username;
      } else {
        this.loggedIn = false;
        this.username = null;
      }
    });
  }

  constructor(
    private storage: Storage,
    private toastController: ToastController,
    private platform: Platform,
  ) {
    if (platform.is('hybrid')) {
      this.urlRoot = 'https://bikeaction.org';
    }
  }
}
