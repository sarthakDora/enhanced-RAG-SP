import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatSliderModule } from '@angular/material/slider';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatSliderModule,
    MatSelectModule,
    MatInputModule,
    MatSlideToggleModule
  ],
  template: `
    <div class="settings-container fade-in">
      <div class="settings-header glass-card">
        <h2 class="gradient-text">Settings</h2>
        <p class="text-muted">Configure your Enhanced RAG System</p>
      </div>

      <!-- Chat Settings -->
      <div class="settings-section glass-card">
        <h3><mat-icon>chat</mat-icon> Chat Settings</h3>
        
        <div class="setting-item">
          <label>Temperature</label>
          <p class="setting-description">Controls randomness in AI responses (0 = deterministic, 1 = very random)</p>
          <mat-slider 
            [min]="0" 
            [max]="1" 
            [step]="0.1" 
            [(ngModel)]="settings.temperature">
            <input matSliderThumb [(ngModel)]="settings.temperature">
          </mat-slider>
          <span class="setting-value">{{ settings.temperature }}</span>
        </div>

        <div class="setting-item">
          <label>Max Tokens</label>
          <p class="setting-description">Maximum length of AI responses</p>
          <mat-form-field appearance="outline">
            <input matInput 
                   type="number" 
                   [(ngModel)]="settings.maxTokens"
                   min="100"
                   max="4000">
          </mat-form-field>
        </div>

        <div class="setting-item">
          <label>Enable RAG</label>
          <p class="setting-description">Use document retrieval to enhance responses</p>
          <mat-slide-toggle [(ngModel)]="settings.useRAG"></mat-slide-toggle>
        </div>
      </div>

      <!-- Search Settings -->
      <div class="settings-section glass-card">
        <h3><mat-icon>search</mat-icon> Search Settings</h3>
        
        <div class="setting-item">
          <label>Top K Results</label>
          <p class="setting-description">Number of initial search results</p>
          <mat-form-field appearance="outline">
            <input matInput 
                   type="number" 
                   [(ngModel)]="settings.topK"
                   min="1"
                   max="50">
          </mat-form-field>
        </div>

        <div class="setting-item">
          <label>Rerank Top K</label>
          <p class="setting-description">Number of results after reranking</p>
          <mat-form-field appearance="outline">
            <input matInput 
                   type="number" 
                   [(ngModel)]="settings.rerankTopK"
                   min="1"
                   max="20">
          </mat-form-field>
        </div>

        <div class="setting-item">
          <label>Similarity Threshold</label>
          <p class="setting-description">Minimum similarity score for search results</p>
          <mat-slider 
            [min]="0" 
            [max]="1" 
            [step]="0.05" 
            [(ngModel)]="settings.similarityThreshold">
            <input matSliderThumb [(ngModel)]="settings.similarityThreshold">
          </mat-slider>
          <span class="setting-value">{{ settings.similarityThreshold }}</span>
        </div>

        <div class="setting-item">
          <label>Reranking Strategy</label>
          <p class="setting-description">Method used to rerank search results</p>
          <mat-form-field appearance="outline">
            <mat-select [(ngModel)]="settings.rerankingStrategy">
              <mat-option value="semantic">Semantic</mat-option>
              <mat-option value="metadata">Metadata</mat-option>
              <mat-option value="financial">Financial</mat-option>
              <mat-option value="hybrid">Hybrid</mat-option>
            </mat-select>
          </mat-form-field>
        </div>
      </div>

      <!-- System Information -->
      <div class="settings-section glass-card">
        <h3><mat-icon>info</mat-icon> System Information</h3>
        
        <div class="info-grid">
          <div class="info-item">
            <label>API Status</label>
            <div class="status" [class.connected]="isConnected">
              <mat-icon>{{ isConnected ? 'check_circle' : 'error' }}</mat-icon>
              <span>{{ isConnected ? 'Connected' : 'Disconnected' }}</span>
            </div>
          </div>

          <div class="info-item">
            <label>Version</label>
            <span>1.0.0</span>
          </div>

          <div class="info-item">
            <label>Environment</label>
            <span>Development</span>
          </div>

          <div class="info-item">
            <label>Last Updated</label>
            <span>{{ lastUpdated }}</span>
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="settings-actions glass-card">
        <button mat-raised-button 
                color="primary"
                class="glass-button"
                (click)="saveSettings()">
          <mat-icon>save</mat-icon>
          Save Settings
        </button>

        <button mat-button 
                class="glass-button"
                (click)="resetSettings()">
          <mat-icon>restore</mat-icon>
          Reset to Defaults
        </button>

        <button mat-button 
                class="glass-button"
                (click)="exportSettings()">
          <mat-icon>download</mat-icon>
          Export Settings
        </button>
      </div>
    </div>
  `,
  styles: [`
    .settings-container {
      max-width: 800px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .settings-header {
      padding: 24px;
    }

    .settings-header h2 {
      margin: 0;
      font-size: 24px;
    }

    .settings-header p {
      margin: 4px 0 0 0;
      font-size: 14px;
    }

    .settings-section {
      padding: 24px;
    }

    .settings-section h3 {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 24px 0;
      font-size: 18px;
      color: var(--text-primary);
    }

    .setting-item {
      margin-bottom: 24px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .setting-item label {
      font-weight: 500;
      color: var(--text-primary);
    }

    .setting-description {
      font-size: 14px;
      color: var(--text-muted);
      margin: 0;
    }

    .setting-value {
      font-size: 14px;
      color: var(--text-secondary);
      margin-top: 4px;
    }

    .mat-mdc-slider {
      width: 100%;
    }

    .mat-mdc-form-field {
      width: 200px;
    }

    .info-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
    }

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .info-item label {
      font-weight: 500;
      color: var(--text-secondary);
      font-size: 14px;
    }

    .info-item span {
      color: var(--text-primary);
    }

    .status {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--text-muted);
    }

    .status.connected {
      color: #4caf50;
    }

    .status mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .settings-actions {
      display: flex;
      gap: 12px;
      padding: 24px;
      flex-wrap: wrap;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .settings-actions {
        flex-direction: column;
      }

      .mat-mdc-form-field {
        width: 100%;
      }

      .info-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class SettingsComponent implements OnInit {
  settings = {
    temperature: 0.1,
    maxTokens: 1000,
    useRAG: true,
    topK: 10,
    rerankTopK: 3,
    similarityThreshold: 0.7,
    rerankingStrategy: 'hybrid'
  };

  isConnected = true;
  lastUpdated = new Date().toLocaleDateString();

  constructor() {}

  ngOnInit() {
    this.loadSettings();
  }

  loadSettings() {
    const saved = localStorage.getItem('ragSettings');
    if (saved) {
      this.settings = { ...this.settings, ...JSON.parse(saved) };
    }
  }

  saveSettings() {
    localStorage.setItem('ragSettings', JSON.stringify(this.settings));
    // Show success message
    console.log('Settings saved:', this.settings);
  }

  resetSettings() {
    this.settings = {
      temperature: 0.1,
      maxTokens: 1000,
      useRAG: true,
      topK: 10,
      rerankTopK: 3,
      similarityThreshold: 0.7,
      rerankingStrategy: 'hybrid'
    };
    this.saveSettings();
  }

  exportSettings() {
    const dataStr = JSON.stringify(this.settings, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'rag-settings.json';
    link.click();
    URL.revokeObjectURL(url);
  }
}