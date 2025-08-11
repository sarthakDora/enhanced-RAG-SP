import { Component, Inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatSliderModule } from '@angular/material/slider';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTabsModule } from '@angular/material/tabs';
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
  selector: 'app-chat-settings-dialog',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatSliderModule,
    MatSelectModule,
    MatInputModule,
    MatSlideToggleModule,
    MatFormFieldModule,
    MatTabsModule
  ],
  template: `
    <div class="chat-settings-dialog">
      <div mat-dialog-title class="dialog-header">
        <mat-icon>tune</mat-icon>
        <span>Chat Settings</span>
        <button mat-icon-button mat-dialog-close class="close-button">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      <div mat-dialog-content class="dialog-content">
        <mat-tab-group animationDuration="300ms">
          
          <!-- Prompt Settings Tab -->
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">code</mat-icon>
              Prompts
            </ng-template>
            
            <div class="tab-content">
              <div class="setting-item">
                <div class="prompt-mode-selection">
                  <div class="mode-option" [class.active]="settings.prompts.use_custom_prompts">
                    <mat-slide-toggle [(ngModel)]="settings.prompts.use_custom_prompts">
                      <strong>Performance Attribution Mode</strong>
                    </mat-slide-toggle>
                    <p class="mode-description">
                      Use specialized prompts for institutional performance attribution analysis with consistent formatting and professional terminology.
                    </p>
                  </div>
                  
                  <div class="mode-option" [class.active]="!settings.prompts.use_custom_prompts">
                    <div class="mode-info">
                      <strong>Regular RAG Q&A Mode</strong>
                      <p class="mode-description">
                        Standard document-based question answering without specialized prompts. Best for general inquiries and flexible responses.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              <div class="prompt-settings" *ngIf="settings.prompts.use_custom_prompts">
                <div class="setting-item">
                  <label>System Prompt</label>
                  <p class="setting-description">
                    Defines the AI's role and expertise for performance attribution analysis
                  </p>
                  <mat-form-field appearance="outline" class="full-width">
                    <textarea matInput 
                              [(ngModel)]="settings.prompts.system_prompt"
                              rows="4"
                              placeholder="Enter system prompt..."
                              class="prompt-textarea">
                    </textarea>
                  </mat-form-field>
                </div>

                <div class="setting-item">
                  <label>Query Processing Instructions</label>
                  <p class="setting-description">
                    Additional instructions for processing performance attribution queries
                  </p>
                  <mat-form-field appearance="outline" class="full-width">
                    <textarea matInput 
                              [(ngModel)]="settings.prompts.query_prompt"
                              rows="3"
                              placeholder="Enter query processing instructions..."
                              class="prompt-textarea">
                    </textarea>
                  </mat-form-field>
                </div>

                <div class="setting-item">
                  <label>Response Format Instructions</label>
                  <p class="setting-description">
                    How responses should be formatted for institutional investors
                  </p>
                  <mat-form-field appearance="outline" class="full-width">
                    <textarea matInput 
                              [(ngModel)]="settings.prompts.response_format_prompt"
                              rows="2"
                              placeholder="Enter response formatting instructions..."
                              class="prompt-textarea">
                    </textarea>
                  </mat-form-field>
                </div>

                <div class="prompt-actions">
                  <button mat-stroked-button (click)="resetToDefaults()">
                    <mat-icon>restore</mat-icon>
                    Reset to Performance Attribution Defaults
                  </button>
                  <button mat-stroked-button (click)="previewCombinedPrompt()">
                    <mat-icon>preview</mat-icon>
                    Preview Combined Prompt
                  </button>
                </div>
              </div>
            </div>
          </mat-tab>

          <!-- Chat Behavior Tab -->
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">chat</mat-icon>
              Behavior
            </ng-template>
            
            <div class="tab-content">
              <div class="setting-item">
                <label>Response Temperature</label>
                <p class="setting-description">
                  Controls creativity vs consistency (0 = deterministic, 1 = creative)
                </p>
                <mat-slider [min]="0" [max]="1" [step]="0.1" [(ngModel)]="settings.temperature">
                  <input matSliderThumb [(ngModel)]="settings.temperature">
                </mat-slider>
                <span class="setting-value">{{ settings.temperature }}</span>
              </div>

              <div class="setting-item">
                <label>Max Response Length</label>
                <p class="setting-description">Maximum tokens in AI responses</p>
                <mat-form-field appearance="outline" class="number-field">
                  <input matInput 
                         type="number" 
                         [(ngModel)]="settings.max_tokens"
                         min="100"
                         max="4000">
                </mat-form-field>
              </div>

              <div class="setting-item">
                <mat-slide-toggle [(ngModel)]="settings.use_rag">
                  Enable Document Search
                </mat-slide-toggle>
                <p class="setting-description">
                  Search uploaded documents to enhance responses with specific data
                </p>
              </div>
            </div>
          </mat-tab>

          <!-- Search Settings Tab -->
          <mat-tab>
            <ng-template mat-tab-label>
              <mat-icon class="tab-icon">search</mat-icon>
              Search
            </ng-template>
            
            <div class="tab-content">
              <div class="setting-item">
                <label>Initial Search Results</label>
                <p class="setting-description">Number of documents to retrieve initially</p>
                <mat-form-field appearance="outline" class="number-field">
                  <input matInput 
                         type="number" 
                         [(ngModel)]="settings.top_k"
                         min="1"
                         max="50">
                </mat-form-field>
              </div>

              <div class="setting-item">
                <label>Final Results After Ranking</label>
                <p class="setting-description">Number of most relevant documents to use</p>
                <mat-form-field appearance="outline" class="number-field">
                  <input matInput 
                         type="number" 
                         [(ngModel)]="settings.rerank_top_k"
                         min="1"
                         max="20">
                </mat-form-field>
              </div>

              <div class="setting-item">
                <label>Relevance Threshold</label>
                <p class="setting-description">Minimum similarity score for search results</p>
                <mat-slider [min]="0" [max]="1" [step]="0.05" [(ngModel)]="settings.similarity_threshold">
                  <input matSliderThumb [(ngModel)]="settings.similarity_threshold">
                </mat-slider>
                <span class="setting-value">{{ settings.similarity_threshold }}</span>
              </div>

              <div class="setting-item">
                <label>Ranking Strategy</label>
                <p class="setting-description">Method for ranking search results</p>
                <mat-form-field appearance="outline" class="full-width">
                  <mat-select [(ngModel)]="settings.reranking_strategy">
                    <mat-option value="semantic">Semantic Similarity</mat-option>
                    <mat-option value="metadata">Metadata-based</mat-option>
                    <mat-option value="financial">Financial Context</mat-option>
                    <mat-option value="hybrid">Hybrid Approach</mat-option>
                  </mat-select>
                </mat-form-field>
              </div>
            </div>
          </mat-tab>
          
        </mat-tab-group>
      </div>

      <div mat-dialog-actions class="dialog-actions">
        <button mat-button mat-dialog-close>
          Cancel
        </button>
        <button mat-raised-button 
                color="primary"
                (click)="saveSettings()"
                [disabled]="isLoading">
          <mat-icon *ngIf="isLoading">hourglass_empty</mat-icon>
          <mat-icon *ngIf="!isLoading">save</mat-icon>
          {{ isLoading ? 'Saving...' : 'Save Settings' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .chat-settings-dialog {
      width: 100%;
      max-width: 700px;
      max-height: 80vh;
    }

    .dialog-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 20px 24px 0 24px;
      margin: 0;
    }

    .dialog-header mat-icon {
      color: var(--primary-color);
    }

    .close-button {
      margin-left: auto;
    }

    .dialog-content {
      padding: 20px 24px;
      max-height: 60vh;
      overflow-y: auto;
    }

    .tab-content {
      padding: 20px 0;
    }

    .tab-icon {
      margin-right: 8px;
    }

    .setting-item {
      margin-bottom: 24px;
    }

    .setting-item label {
      display: block;
      font-weight: 500;
      color: var(--text-primary);
      margin-bottom: 4px;
    }

    .setting-description {
      font-size: 13px;
      color: var(--text-muted);
      margin: 4px 0 12px 0;
      line-height: 1.4;
    }

    .setting-header {
      display: flex;
      align-items: center;
      margin-bottom: 8px;
    }

    .setting-value {
      font-size: 14px;
      color: var(--text-secondary);
      margin-left: 12px;
    }

    .full-width {
      width: 100%;
    }

    .number-field {
      width: 120px;
    }

    .prompt-textarea {
      font-family: 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.4;
    }

    .prompt-settings {
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      margin-top: 16px;
      background: var(--surface-color);
    }

    .prompt-actions {
      display: flex;
      gap: 12px;
      margin-top: 20px;
      flex-wrap: wrap;
    }

    .prompt-mode-selection {
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 0;
      background: var(--surface-color);
      overflow: hidden;
    }

    .mode-option {
      padding: 16px;
      transition: all 0.3s ease;
      border-bottom: 1px solid var(--border-color);
    }

    .mode-option:last-child {
      border-bottom: none;
    }

    .mode-option.active {
      background: rgba(59, 130, 246, 0.1);
      border-left: 4px solid #3b82f6;
    }

    .mode-option strong {
      display: block;
      margin-bottom: 8px;
      color: var(--text-primary);
      font-size: 15px;
    }

    .mode-description {
      margin: 0;
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.4;
    }

    .mode-info {
      margin-left: 0;
    }

    .dialog-actions {
      padding: 0 24px 20px 24px;
      display: flex;
      justify-content: flex-end;
      gap: 12px;
    }

    .mat-mdc-slider {
      width: 100%;
    }

    /* Responsive adjustments */
    @media (max-width: 600px) {
      .chat-settings-dialog {
        width: 100vw;
        max-width: 100vw;
        height: 100vh;
        max-height: 100vh;
      }

      .prompt-actions {
        flex-direction: column;
      }

      .dialog-actions {
        flex-direction: column;
      }
    }
  `]
})
export class ChatSettingsDialogComponent implements OnInit {
  settings: ChatSettings = {
    temperature: 0.1,
    max_tokens: 1000,
    use_rag: true,
    top_k: 10,
    rerank_top_k: 3,
    similarity_threshold: 0.7,
    reranking_strategy: 'hybrid',
    prompts: {
      use_custom_prompts: true,  // Enable by default for performance attribution
      system_prompt: '',
      query_prompt: '',
      response_format_prompt: ''
    }
  };

  isLoading = false;

  constructor(
    public dialogRef: MatDialogRef<ChatSettingsDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { sessionId?: string },
    private apiService: ApiService
  ) {}

  ngOnInit() {
    this.loadSettings();
  }

  loadSettings() {
    this.isLoading = true;
    this.apiService.getSettings(this.data.sessionId).subscribe({
      next: (response) => {
        this.settings = response;
        this.isLoading = false;
        console.log('Chat settings loaded:', this.settings);
      },
      error: (error) => {
        console.error('Failed to load settings, using defaults:', error);
        this.loadDefaultPrompts();
        this.isLoading = false;
      }
    });
  }

  loadDefaultPrompts() {
    this.apiService.getDefaultPrompts().subscribe({
      next: (response) => {
        this.settings.prompts.system_prompt = response.system_prompt;
        this.settings.prompts.query_prompt = response.query_prompt;
        this.settings.prompts.response_format_prompt = response.response_format_prompt;
        console.log('Default prompts loaded for chat settings');
      },
      error: (error) => {
        console.error('Failed to load default prompts:', error);
      }
    });
  }

  resetToDefaults() {
    this.loadDefaultPrompts();
  }

  previewCombinedPrompt() {
    if (!this.settings.prompts.use_custom_prompts) {
      return;
    }

    const systemPrompt = this.settings.prompts.system_prompt.trim();
    const queryPrompt = this.settings.prompts.query_prompt.trim();
    const formatPrompt = this.settings.prompts.response_format_prompt.trim();
    
    const combinedPrompt = [
      systemPrompt ? `=== SYSTEM PROMPT ===\n${systemPrompt}` : '',
      queryPrompt ? `=== QUERY PROCESSING ===\n${queryPrompt}` : '',
      formatPrompt ? `=== RESPONSE FORMAT ===\n${formatPrompt}` : ''
    ].filter(section => section.length > 0).join('\n\n');
    
    if (!combinedPrompt.trim()) {
      alert('No custom prompts to preview. Please configure your prompts first.');
      return;
    }

    // Create backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'prompt-preview-backdrop';
    backdrop.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.5); z-index: 20000;
      display: flex; align-items: center; justify-content: center;
      padding: 20px; backdrop-filter: blur(4px);
    `;
    
    // Create dialog
    const dialog = document.createElement('div');
    dialog.style.cssText = `
      background: rgba(255, 255, 255, 0.98); backdrop-filter: blur(20px);
      border-radius: 16px; max-width: 90vw; max-height: 85vh; width: 800px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      border: 1px solid rgba(255, 255, 255, 0.3);
      display: flex; flex-direction: column; overflow: hidden;
    `;
    
    dialog.innerHTML = `
      <div style="padding: 24px 24px 16px; border-bottom: 1px solid rgba(0, 0, 0, 0.1); flex-shrink: 0;">
        <h3 style="margin: 0; color: #2d3748; display: flex; align-items: center; gap: 12px; font-size: 18px;">
          <span style="color: #3b82f6;">📋</span>
          Combined Prompt Preview
        </h3>
        <p style="margin: 8px 0 0; color: #718096; font-size: 14px;">
          This is how your custom prompts will be structured for the LLM
        </p>
      </div>
      <div style="flex: 1; overflow-y: auto; padding: 0;">
        <pre style="margin: 0; padding: 24px; white-space: pre-wrap; font-family: 'Monaco', 'Menlo', 'Courier New', monospace; font-size: 13px; line-height: 1.5; background: #f8fafc; color: #2d3748; overflow-wrap: break-word;">${combinedPrompt}</pre>
      </div>
      <div style="padding: 16px 24px; border-top: 1px solid rgba(0, 0, 0, 0.1); text-align: right; flex-shrink: 0;">
        <button class="close-preview-btn" style="padding: 10px 20px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500; transition: background 0.2s;">
          Close Preview
        </button>
      </div>
    `;
    
    backdrop.appendChild(dialog);
    document.body.appendChild(backdrop);

    // Add click handlers
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        document.body.removeChild(backdrop);
      }
    });

    dialog.querySelector('.close-preview-btn')?.addEventListener('click', () => {
      document.body.removeChild(backdrop);
    });

    // Add escape key handler
    const escHandler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        document.body.removeChild(backdrop);
        document.removeEventListener('keydown', escHandler);
      }
    };
    document.addEventListener('keydown', escHandler);
  }

  saveSettings() {
    this.isLoading = true;
    this.apiService.updateSettings(this.settings, this.data.sessionId).subscribe({
      next: (response) => {
        console.log('Settings saved successfully:', response);
        this.isLoading = false;
        this.dialogRef.close({ saved: true, settings: this.settings });
      },
      error: (error) => {
        console.error('Failed to save settings:', error);
        this.isLoading = false;
      }
    });
  }
}