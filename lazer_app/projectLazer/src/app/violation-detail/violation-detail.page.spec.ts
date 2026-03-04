import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { ServiceWorkerModule } from '@angular/service-worker';
import { IonicModule } from '@ionic/angular';
import { IonicStorageModule, Storage } from '@ionic/storage-angular';
import { ViolationDetailPage } from './violation-detail.page';

describe('ViolationDetailPage', () => {
  let component: ViolationDetailPage;
  let fixture: ComponentFixture<ViolationDetailPage>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ViolationDetailPage],
      imports: [
        IonicModule.forRoot(),
        IonicStorageModule.forRoot(),
        ServiceWorkerModule.register('', { enabled: false }),
      ],
      providers: [provideRouter([])],
    }).compileComponents();

    const storage = TestBed.inject(Storage);
    await storage.create();

    fixture = TestBed.createComponent(ViolationDetailPage);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
