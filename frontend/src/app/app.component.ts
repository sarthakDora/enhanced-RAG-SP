import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterModule, Router, NavigationEnd } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSidenavModule } from '@angular/material/sidenav';
import { ApiService } from './services/api.service';
import { Subscription, filter } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterModule,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatSidenavModule
  ],
  template: `
    <div class="app-container">
      <mat-sidenav-container class="sidenav-container">
        <!-- Sidebar -->
        <mat-sidenav 
          #drawer 
          class="sidenav glass-card" 
          fixedInViewport="true"
          [opened]="false"
          mode="over">
          <div class="sidenav-content">
            <div class="logo-section">
              <h2 class="gradient-text">Enhanced RAG</h2>
              <p class="text-muted">Financial AI Assistant</p>
            </div>
            
            <nav class="navigation">
              <a routerLink="/chat" 
                 routerLinkActive="active" 
                 class="nav-item glass-button">
                <mat-icon>chat</mat-icon>
                <span>Chat</span>
              </a>
              
              <a routerLink="/documents" 
                 routerLinkActive="active" 
                 class="nav-item glass-button">
                <mat-icon>description</mat-icon>
                <span>Documents</span>
                <div *ngIf="hasDocumentUpdates" class="update-indicator" title="New documents available">
                  <mat-icon>fiber_new</mat-icon>
                </div>
              </a>
              
              <a routerLink="/attribution" 
                 routerLinkActive="active" 
                 class="nav-item glass-button">
                <mat-icon>account_balance</mat-icon>
                <span>Attribution</span>
              </a>
              
              <a routerLink="/analytics" 
                 routerLinkActive="active" 
                 class="nav-item glass-button">
                <mat-icon>analytics</mat-icon>
                <span>Analytics</span>
              </a>
              
              <a routerLink="/settings" 
                 routerLinkActive="active" 
                 class="nav-item glass-button">
                <mat-icon>settings</mat-icon>
                <span>Settings</span>
              </a>
            </nav>
          </div>
        </mat-sidenav>

        <!-- Main Content -->
        <mat-sidenav-content>
          <!-- Top Navigation -->
          <mat-toolbar class="toolbar glass-card">
            <button
              type="button"
              aria-label="Toggle sidenav"
              mat-icon-button
              (click)="drawer.toggle()"
              class="menu-button glass-button">
              <mat-icon aria-label="Side nav toggle icon">menu</mat-icon>
            </button>
            
            <span class="toolbar-title gradient-text">Enhanced RAG System</span>
            
            <div class="toolbar-spacer"></div>
            
            <!-- Status Indicator -->
            <div class="status-indicator" [class.connected]="isConnected">
              <mat-icon>circle</mat-icon>
              <span>{{ isConnected ? 'Connected' : 'Disconnected' }}</span>
            </div>
          </mat-toolbar>

          <!-- Router Outlet -->
          <main class="main-content">
            <router-outlet></router-outlet>
          </main>
        </mat-sidenav-content>
      </mat-sidenav-container>
    </div>
  `,
  styles: [`
    .app-container {
      height: 100vh;
      background: var(--bg-primary);
    }

    .sidenav-container {
      height: 100%;
    }

    .sidenav {
      width: 280px;
      margin: 16px;
      height: calc(100vh - 32px);
      border-radius: 16px !important;
      background: var(--glass-primary) !important;
      backdrop-filter: blur(16px) !important;
    }

    .sidenav-content {
      padding: 24px;
      height: 100%;
      display: flex;
      flex-direction: column;
    }

    .logo-section {
      text-align: center;
      margin-bottom: 32px;
      padding-bottom: 24px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }

    .logo-section h2 {
      font-size: 24px;
      margin-bottom: 4px;
    }

    .navigation {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .nav-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px 20px;
      text-decoration: none;
      color: var(--text-primary);
      border-radius: 12px;
      transition: all 0.3s ease;
      background: transparent;
      border: 1px solid transparent;
    }

    .nav-item:hover {
      background: var(--glass-accent);
      transform: translateX(4px);
    }

    .nav-item.active {
      background: var(--glass-accent);
      border-color: rgba(255, 255, 255, 0.3);
    }

    .update-indicator {
      margin-left: auto;
      background: #f44336;
      border-radius: 50%;
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      animation: pulse 2s infinite;
    }

    .update-indicator mat-icon {
      font-size: 12px;
      width: 12px;
      height: 12px;
      color: white;
    }

    @keyframes pulse {
      0% {
        box-shadow: 0 0 0 0 rgba(244, 67, 54, 0.7);
      }
      70% {
        box-shadow: 0 0 0 10px rgba(244, 67, 54, 0);
      }
      100% {
        box-shadow: 0 0 0 0 rgba(244, 67, 54, 0);
      }
    }

    .toolbar {
      position: sticky;
      top: 0;
      z-index: 1000;
      margin: 16px;
      border-radius: 16px !important;
      background: var(--glass-primary) !important;
      backdrop-filter: blur(16px) !important;
      border: var(--border-glass) !important;
      height: 64px;
    }

    .menu-button {
      margin-right: 16px;
    }

    .toolbar-title {
      font-size: 20px;
      font-weight: 600;
    }

    .toolbar-spacer {
      flex: 1 1 auto;
    }

    .status-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 20px;
      background: var(--glass-secondary);
      color: var(--text-muted);
      font-size: 14px;
    }

    .status-indicator.connected {
      color: #4caf50;
    }

    .status-indicator mat-icon {
      font-size: 12px;
      width: 12px;
      height: 12px;
    }

    .main-content {
      padding: 0 16px 16px 16px;
      min-height: calc(100vh - 96px);
    }

    @media (max-width: 768px) {
      .sidenav {
        width: 240px;
      }
      
      .toolbar {
        margin: 8px;
      }
      
      .main-content {
        padding: 0 8px 8px 8px;
      }
    }
  `]
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'Enhanced RAG System';
  isConnected = true;
  hasDocumentUpdates = false;
  private subscriptions: Subscription[] = [];

  constructor(private apiService: ApiService, private router: Router) {
    // You can add connection status monitoring here
    this.checkConnectionStatus();
  }

  ngOnInit() {
    // Subscribe to document updates
    const docUpdateSub = this.apiService.documentsUpdated$.subscribe(() => {
      this.hasDocumentUpdates = true;
    });
    this.subscriptions.push(docUpdateSub);

    // Clear the update indicator when navigating to documents page
    const routerSub = this.router.events.pipe(
      filter((event): event is NavigationEnd => event instanceof NavigationEnd)
    ).subscribe((event) => {
      if (event.urlAfterRedirects === '/documents') {
        this.hasDocumentUpdates = false;
      }
    });
    this.subscriptions.push(routerSub);
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  private checkConnectionStatus() {
    // Initial health check
    this.performHealthCheck();
    
    // Use ApiService for periodic health check with correct backend URL
    setInterval(() => {
      this.performHealthCheck();
    }, 30000); // Check every 30 seconds
  }

  private performHealthCheck() {
    this.apiService.checkHealth().subscribe({
      next: () => {
        this.isConnected = true;
      },
      error: () => {
        this.isConnected = false;
      }
    });
  }
}