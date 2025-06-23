import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'org.bikeaction.laser',
  appName: 'Laser Vision',
  webDir: 'www',

  server: {
    hostname: 'laser.bikeaction.org',
    androidScheme: 'https',
  }

};

export default config;
