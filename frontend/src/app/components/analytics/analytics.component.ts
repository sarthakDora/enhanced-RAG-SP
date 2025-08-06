import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-analytics',
  standalone: true,
  imports: [CommonModule, MatCardModule, MatIconModule, MatButtonModule],
  template: `
    <div class="analytics-container fade-in">
      <div class="analytics-header glass-card">
        <h2 class="gradient-text">Analytics Dashboard</h2>
        <p class="text-muted">Performance metrics and insights</p>
      </div>

      <div class="coming-soon glass-card">
        <mat-icon class="coming-soon-icon">analytics</mat-icon>
        <h3>Analytics Coming Soon</h3>
        <p>Advanced analytics and reporting features will be available in the next update.</p>
        <button mat-raised-button class="glass-button">
          <mat-icon>notifications</mat-icon>
          Notify Me
        </button>
      </div>
    </div>
  `,
  styles: [`
    .analytics-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .analytics-header {
      padding: 24px;
    }

    .analytics-header h2 {
      margin: 0;
      font-size: 24px;
    }

    .analytics-header p {
      margin: 4px 0 0 0;
      font-size: 14px;
    }

    .coming-soon {
      text-align: center;
      padding: 64px 32px;
    }

    .coming-soon-icon {
      font-size: 80px;
      width: 80px;
      height: 80px;
      color: var(--text-muted);
      margin-bottom: 24px;
    }

    .coming-soon h3 {
      margin: 0 0 16px 0;
      font-size: 24px;
      color: var(--text-secondary);
    }

    .coming-soon p {
      margin: 0 0 32px 0;
      color: var(--text-muted);
      max-width: 400px;
      margin-left: auto;
      margin-right: auto;
    }
  `]
})
export class AnalyticsComponent implements OnInit {
  constructor() {}

  ngOnInit() {}
}