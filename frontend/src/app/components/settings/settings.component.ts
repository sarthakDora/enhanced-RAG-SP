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
import { MatFormFieldModule } from '@angular/material/form-field';
import { ApiService } from '../../services/api.service';

interface ChatSettings {
  temperature: number;
  max_tokens: number;
  use_rag: boolean;
  top_k: number;
  rerank_top_k: number;
  similarity_threshold: number;
  reranking_strategy: string;
  prompts: {
    use_custom_prompts: boolean;
    system_prompt: string;
    query_prompt: string;
    response_format_prompt: string;
  };
}

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
    MatSlideToggleModule,
    MatFormFieldModule
  ],
  template: `
    <div class="settings-container fade-in">
      <div class="settings-header glass-card">
        <h2 class="gradient-text">Settings</h2>
  <p class="text-muted">Configure your VBAM RAG System</p>
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
                   [(ngModel)]="settings.max_tokens"
                   min="100"
                   max="4000">
          </mat-form-field>
        </div>

        <div class="setting-item">
          <label>Enable RAG</label>
          <p class="setting-description">Use document retrieval to enhance responses</p>
          <mat-slide-toggle [(ngModel)]="settings.use_rag"></mat-slide-toggle>
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
                   [(ngModel)]="settings.top_k"
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
                   [(ngModel)]="settings.rerank_top_k"
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
            [(ngModel)]="settings.similarity_threshold">
            <input matSliderThumb [(ngModel)]="settings.similarity_threshold">
          </mat-slider>
          <span class="setting-value">{{ settings.similarity_threshold }}</span>
        </div>

        <div class="setting-item">
          <label>Reranking Strategy</label>
          <p class="setting-description">Method used to rerank search results</p>
          <mat-form-field appearance="outline">
            <mat-select [(ngModel)]="settings.reranking_strategy">
              <mat-option value="semantic">Semantic</mat-option>
              <mat-option value="metadata">Metadata</mat-option>
              <mat-option value="financial">Financial</mat-option>
              <mat-option value="hybrid">Hybrid</mat-option>
            </mat-select>
          </mat-form-field>
        </div>
      </div>

      <!-- Prompt Settings Info -->
      <div class="settings-section glass-card">
        <h3><mat-icon>code</mat-icon> Prompt Settings</h3>
        <div class="info-message">
          <mat-icon>info</mat-icon>
          <div>
            <h4>Chat-Specific Prompt Customization</h4>
            <p>Prompt settings for performance attribution analysis are now available directly in each chat session. Click the settings button (⚙️) in any chat to customize prompts for that conversation.</p>
            <p><strong>Benefits:</strong></p>
            <ul>
              <li>Session-specific prompt customization</li>
              <li>Real-time prompt updates</li>
              <li>Performance attribution focused defaults</li>
            </ul>
          </div>
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

      .textarea-field {
        width: 100%;
      }

      .textarea-field textarea {
        min-height: 80px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.4;
      }

      .prompt-actions {
        display: flex;
        gap: 12px;
        margin-top: 16px;
        flex-wrap: wrap;
      }

      .info-grid {
        grid-template-columns: 1fr;
      }
    }

    .info-message {
      display: flex;
      gap: 16px;
      align-items: flex-start;
      padding: 16px;
      background: rgba(59, 130, 246, 0.1);
      border: 1px solid rgba(59, 130, 246, 0.2);
      border-radius: 8px;
      color: var(--text-primary);
    }

    .info-message mat-icon {
      color: #3b82f6;
      margin-top: 2px;
    }

    .info-message h4 {
      margin: 0 0 8px 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
    }

    .info-message p {
      margin: 0 0 8px 0;
      line-height: 1.5;
    }

    .info-message ul {
      margin: 8px 0 0 16px;
      padding: 0;
    }

    .info-message li {
      margin-bottom: 4px;
      line-height: 1.4;
    }
  `]
})
export class SettingsComponent implements OnInit {
  settings: ChatSettings = {
    temperature: 0.1,
    max_tokens: 1000,
    use_rag: true,
    top_k: 10,
    rerank_top_k: 3,
    similarity_threshold: 0.7,
    reranking_strategy: 'hybrid',
    prompts: {
      use_custom_prompts: false,
      system_prompt: '',
      query_prompt: '',
      response_format_prompt: ''
    }
  };

  isConnected = true;
  lastUpdated = new Date().toLocaleDateString();

  constructor(private apiService: ApiService) {}

  ngOnInit() {
    this.loadSettings();
  }

  loadSettings() {
    this.apiService.getSettings().subscribe({
      next: (response) => {
        this.settings = response;
        console.log('Settings loaded from backend:', this.settings);
      },
      error: (error) => {
        console.error('Failed to load settings from backend, using defaults:', error);
        // Load default performance attribution prompts
        this.loadDefaultPrompts();
      }
    });
  }

  loadDefaultPrompts() {
    this.apiService.getDefaultPrompts().subscribe({
      next: (response) => {
        this.settings.prompts.system_prompt = response.system_prompt;
        this.settings.prompts.query_prompt = response.query_prompt;
        this.settings.prompts.response_format_prompt = response.response_format_prompt;
        console.log('Default prompts loaded:', response);
      },
      error: (error) => {
        console.error('Failed to load default prompts:', error);
      }
    });
  }

  saveSettings() {
    this.apiService.updateSettings(this.settings).subscribe({
      next: (response) => {
        console.log('Settings saved successfully:', response);
        // Show success message to user
      },
      error: (error) => {
        console.error('Failed to save settings:', error);
        // Show error message to user
      }
    });
  }

  resetSettings() {
    this.settings = {
      temperature: 0.1,
      max_tokens: 1000,
      use_rag: true,
      top_k: 10,
      rerank_top_k: 3,
      similarity_threshold: 0.7,
      reranking_strategy: 'hybrid',
      prompts: {
        use_custom_prompts: false,
        system_prompt: '',
        query_prompt: '',
        response_format_prompt: ''
      }
    };
    this.loadDefaultPrompts();
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