import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';

import { ApiService } from '../../services/api.service';

interface AttributionSession {
  session_id: string;
  collection_name: string;
  chunks_created: number;
  period: string;
  asset_class: string;
  attribution_level: string;
  upload_timestamp: string;
  filename: string;
  chunks?: any[];
}

interface AttributionResponse {
  mode: 'qa' | 'commentary';
  response: string;
  session_id: string;
  question?: string;
  context_used?: number;
}

@Component({
  selector: 'app-attribution',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatInputModule,
    MatSelectModule,
    MatProgressBarModule,
    MatChipsModule,
    MatTabsModule,
    MatDividerModule
  ],
  template: `
    <div class="attribution-container fade-in">
      <!-- Header -->
      <div class="attribution-header glass-card">
        <div>
          <h2 class="gradient-text">Performance Attribution Analysis</h2>
          <p class="text-muted">Upload Excel attribution files and generate professional commentary or ask specific questions</p>
        </div>
        
        <div class="header-actions">
          <button mat-raised-button 
                  class="glass-button"
                  (click)="triggerFileInput()">
            <mat-icon>upload_file</mat-icon>
            Upload Attribution File
          </button>
        </div>
      </div>

      <!-- Upload Section -->
      <div class="upload-section glass-card">
        <h3>Upload Attribution Excel File</h3>
        <p class="section-description">
          Upload Excel files with performance attribution data (Equity sectors or Fixed Income countries).
          Supported formats: .xlsx, .xls
        </p>

        <!-- File Upload Area -->
        <div class="upload-area"
             [class.dragover]="isDragOver"
             (dragover)="onDragOver($event)"
             (dragleave)="onDragLeave($event)"
             (drop)="onDrop($event)"
             (click)="triggerFileInput()">
          
          <input #fileInput 
                 type="file" 
                 accept=".xlsx,.xls"
                 (change)="onFileSelected($event)"
                 style="display: none;">
          
          <div class="upload-content">
            <mat-icon class="upload-icon">table_view</mat-icon>
            <h4>Drop Attribution Excel File Here</h4>
            <p>Or click to browse</p>
            <div class="supported-formats">
              <mat-chip>Equity Sectors</mat-chip>
              <mat-chip>Fixed Income Countries</mat-chip>
              <mat-chip>.xlsx/.xls</mat-chip>
            </div>
          </div>
        </div>

        <!-- Upload Configuration -->
        <div class="upload-config" *ngIf="selectedFile">
          <h4>File Selected: {{ selectedFile.name }}</h4>
          
          <div class="config-row">
            <mat-form-field appearance="outline">
              <mat-label>Session ID (optional)</mat-label>
              <input matInput [(ngModel)]="sessionId" placeholder="Auto-generated if empty">
            </mat-form-field>
          </div>

          <div class="upload-actions">
            <button mat-raised-button 
                    color="primary"
                    class="glass-button"
                    [disabled]="isUploading"
                    (click)="uploadFile()">
              <mat-icon>analytics</mat-icon>
              Process Attribution File
            </button>
            
            <button mat-button 
                    class="glass-button"
                    (click)="clearSelection()">
              <mat-icon>clear</mat-icon>
              Clear
            </button>
          </div>
        </div>

        <!-- Upload Progress -->
        <div class="upload-progress" *ngIf="isUploading">
          <h4>Processing Attribution File...</h4>
          <mat-progress-bar mode="indeterminate"></mat-progress-bar>
          <p class="progress-text">Parsing Excel data, detecting asset class, and building attribution chunks...</p>
        </div>

        <!-- Upload Results -->
        <div class="upload-results" *ngIf="uploadResult">
          <h4>✅ Attribution File Processed Successfully</h4>
          <div class="result-grid">
            <div class="result-item">
              <strong>Session ID:</strong> {{ uploadResult?.session_id }}
            </div>
            <div class="result-item">
              <strong>Asset Class:</strong> {{ uploadResult?.asset_class }}
            </div>
            <div class="result-item">
              <strong>Attribution Level:</strong> {{ uploadResult?.attribution_level }}
            </div>
            <div class="result-item">
              <strong>Period:</strong> {{ uploadResult?.period }}
            </div>
            <div class="result-item">
              <strong>Chunks Created:</strong> {{ uploadResult?.chunks_created }}
            </div>
            <div class="result-item">
              <strong>Collection:</strong> {{ uploadResult?.collection_name }}
            </div>
          </div>
        </div>
      </div>

      <!-- Chunks Viewer Section -->
      <div class="chunks-section glass-card" *ngIf="chunkList && chunkList.length">
        <h3>Attribution Chunks</h3>
        <div class="chunks-grid">
          <div *ngFor="let chunk of chunkList; let i = index" class="chunk-card">
            <div class="chunk-header" (click)="chunk.expanded = !chunk.expanded">
              <mat-icon>{{ chunk.expanded ? 'expand_less' : 'expand_more' }}</mat-icon>
              <span><strong>Chunk {{ i + 1 }}</strong> - {{ chunk.filename }}</span>
              <span class="chunk-meta">{{ chunk.document_type }}</span>
            </div>
            <div class="chunk-content" *ngIf="chunk.expanded">
              <pre>{{ chunk.content }}</pre>
            </div>
          </div>
        </div>
      </div>

      <!-- Analysis Section -->
      <div class="analysis-section" *ngIf="uploadResult">
        <mat-tab-group>
          <!-- Commentary Mode Tab -->
          <mat-tab label="Commentary Mode">
            <div class="tab-content">
              <div class="mode-description glass-card">
                <mat-icon>article</mat-icon>
                <div>
                  <h4>Professional Attribution Commentary</h4>
                  <p>Generate institutional-grade performance attribution commentary using the uploaded data. 
                     Uses predefined system prompts optimized for portfolio managers and senior analysts.</p>
                </div>
              </div>

              <div class="commentary-controls glass-card">
                <div class="control-row">
                  <mat-form-field appearance="outline">
                    <mat-label>Period (optional)</mat-label>
                    <input matInput [(ngModel)]="commentaryPeriod" 
                           placeholder="e.g., Q2 2025"
                           [value]="uploadResult?.period">
                  </mat-form-field>
                  
                  <button mat-raised-button 
                          color="primary"
                          class="glass-button"
                          [disabled]="isGeneratingCommentary"
                          (click)="generateCommentary()">
                    <mat-icon>auto_awesome</mat-icon>
                    Generate Commentary
                  </button>
                </div>

                <div class="progress-indicator" *ngIf="isGeneratingCommentary">
                  <mat-progress-bar mode="indeterminate"></mat-progress-bar>
                  <p>Generating professional attribution commentary...</p>
                </div>
              </div>

              <!-- Commentary Results -->
              <div class="commentary-results glass-card" *ngIf="commentaryResponse">
                <div class="results-header">
                  <h4>Attribution Commentary</h4>
                  <div class="result-meta">
                    <span>Mode: {{ commentaryResponse.mode }}</span>
                    <span>Session: {{ commentaryResponse.session_id }}</span>
                    <span *ngIf="commentaryResponse.context_used">Context: {{ commentaryResponse.context_used }} chunks</span>
                  </div>
                </div>
                
                <div class="prompt-preview-box" *ngIf="commentaryPrompt">
                  <h5>Prompt Sent to LLM</h5>
                  <textarea readonly rows="10" style="width:100%;font-size:12px;background:#f5f5f5;border-radius:6px;padding:8px;">{{ commentaryPrompt }}</textarea>
                </div>
                
                <div class="commentary-content" [innerHTML]="formatCommentary(commentaryResponse.response)">
                </div>
                
                <div class="results-actions">
                  <button mat-button class="glass-button" (click)="copyToClipboard(commentaryResponse.response)">
                    <mat-icon>content_copy</mat-icon>
                    Copy Commentary
                  </button>
                </div>
              </div>
            </div>
          </mat-tab>

          <!-- Q&A Mode Tab -->
          <mat-tab label="Q&A Mode">
            <div class="tab-content">
              <div class="mode-description glass-card">
                <mat-icon>quiz</mat-icon>
                <div>
                  <h4>Attribution Q&A</h4>
                  <p>Ask specific questions about the attribution data. 
                     Answers are strictly based on the uploaded document context - no hallucination.</p>
                </div>
              </div>

              <!-- Sample Questions -->
              <div class="sample-questions glass-card">
                <h4>Sample Questions</h4>
                <div class="questions-grid">
                  <button mat-stroked-button 
                          class="sample-question"
                          *ngFor="let question of sampleQuestions"
                          (click)="setQuestion(question)">
                    {{ question }}
                  </button>
                </div>
              </div>

              <!-- Q&A Interface -->
              <div class="qa-interface glass-card">
                <mat-form-field appearance="outline" class="question-input">
                  <mat-label>Ask a question about the attribution data</mat-label>
                  <textarea matInput 
                            [(ngModel)]="currentQuestion"
                            rows="3"
                            placeholder="e.g., Which sectors had positive allocation effect?">
                  </textarea>
                </mat-form-field>
                
                <button mat-raised-button 
                        color="primary"
                        class="glass-button ask-button"
                        [disabled]="!currentQuestion.trim() || isAnswering"
                        (click)="askQuestion()">
                  <mat-icon>send</mat-icon>
                  Ask Question
                </button>

                <div class="progress-indicator" *ngIf="isAnswering">
                  <mat-progress-bar mode="indeterminate"></mat-progress-bar>
                  <p>Searching attribution data and generating answer...</p>
                </div>
              </div>

              <!-- Q&A History -->
              <div class="qa-history" *ngIf="qaHistory.length > 0">
                <h4>Q&A History</h4>
                <div *ngFor="let qa of qaHistory; trackBy: trackByIndex" 
                     class="qa-item glass-card">
                  <div class="question">
                    <mat-icon>help_outline</mat-icon>
                    <strong>Q:</strong> {{ qa.question }}
                  </div>
                  <mat-divider></mat-divider>
                  <div class="answer">
                    <mat-icon>lightbulb</mat-icon>
                    <strong>A:</strong> {{ qa.response }}
                  </div>
                  <div class="qa-meta">
                    <span>Context used: {{ qa.context_used || 0 }} chunks</span>
                    <button mat-icon-button (click)="copyToClipboard(qa.response)">
                      <mat-icon>content_copy</mat-icon>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </mat-tab>
        </mat-tab-group>
      </div>

      <!-- Active Sessions -->
      <div class="sessions-section glass-card" *ngIf="activeSessions.length > 0">
        <h3>Active Attribution Sessions</h3>
        <div class="sessions-grid">
          <div *ngFor="let session of activeSessions" 
               class="session-card"
               [class.active]="session.session_id === uploadResult?.session_id">
            <div class="session-header">
              <mat-icon>analytics</mat-icon>
              <div class="session-title">
                <h4>{{ session.filename }}</h4>
                <p>{{ session.asset_class }} - {{ session.attribution_level }}</p>
              </div>
              <button mat-icon-button 
                      color="warn"
                      (click)="clearSession(session.session_id)">
                <mat-icon>delete</mat-icon>
              </button>
            </div>
            
            <div class="session-details">
              <span>{{ session.period }}</span>
              <span>{{ session.chunks_created }} chunks</span>
              <span>{{ formatDate(session.upload_timestamp) }}</span>
            </div>
            
            <div class="session-actions">
              <button mat-button 
                      class="glass-button"
                      (click)="switchToSession(session)">
                <mat-icon>switch_account</mat-icon>
                Switch to Session
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .attribution-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .attribution-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 24px;
    }

    .attribution-header h2 {
      margin: 0;
      font-size: 24px;
    }

    .attribution-header p {
      margin: 4px 0 0 0;
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }

    .upload-section, .analysis-section, .sessions-section {
      padding: 24px;
    }

    .section-description {
      color: var(--text-secondary);
      margin: 0 0 20px 0;
      font-size: 14px;
    }

    .upload-area {
      padding: 48px 24px;
      text-align: center;
      cursor: pointer;
      transition: all 0.3s ease;
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 16px;
      background: var(--glass-secondary);
      margin-bottom: 20px;
    }

    .upload-area:hover,
    .upload-area.dragover {
      border-color: rgba(255, 255, 255, 0.6);
      background: var(--glass-accent) !important;
      transform: scale(1.02);
    }

    .upload-content .upload-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: var(--text-primary);
      margin-bottom: 16px;
    }

    .upload-content h4 {
      margin: 0 0 8px 0;
      font-size: 18px;
    }

    .upload-content p {
      margin: 4px 0 16px 0;
      color: var(--text-secondary);
    }

    .supported-formats {
      display: flex;
      gap: 8px;
      justify-content: center;
      flex-wrap: wrap;
    }

    .upload-config {
      background: var(--glass-secondary);
      padding: 20px;
      border-radius: 12px;
      margin-bottom: 20px;
    }

    .upload-config h4 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .config-row {
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }

    .upload-actions {
      display: flex;
      gap: 12px;
    }

    .upload-progress {
      background: var(--glass-secondary);
      padding: 20px;
      border-radius: 12px;
      text-align: center;
    }

    .progress-text {
      margin: 12px 0 0 0;
      font-size: 14px;
      color: var(--text-secondary);
    }

    .upload-results {
      background: rgba(76, 175, 80, 0.1);
      border: 1px solid rgba(76, 175, 80, 0.3);
      padding: 20px;
      border-radius: 12px;
      margin-top: 20px;
    }

    .upload-results h4 {
      margin: 0 0 16px 0;
      color: #4caf50;
    }

    .result-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }

    .result-item {
      font-size: 14px;
    }

    .tab-content {
      padding: 24px 0;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }

    .mode-description {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
    }

    .mode-description mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: var(--text-primary);
    }

    .mode-description h4 {
      margin: 0 0 8px 0;
      font-size: 16px;
    }

    .mode-description p {
      margin: 0;
      color: var(--text-secondary);
      font-size: 14px;
    }

    .commentary-controls {
      padding: 20px;
    }

    .control-row {
      display: flex;
      gap: 16px;
      align-items: end;
    }

    .control-row mat-form-field {
      flex: 1;
    }

    .progress-indicator {
      margin-top: 16px;
    }

    .progress-indicator p {
      margin: 8px 0 0 0;
      font-size: 14px;
      color: var(--text-secondary);
      text-align: center;
    }

    .commentary-results {
      padding: 24px;
    }

    .results-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .results-header h4 {
      margin: 0;
      font-size: 18px;
    }

    .result-meta {
      display: flex;
      gap: 16px;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .commentary-content {
      background: var(--glass-secondary);
      padding: 20px;
      border-radius: 8px;
      line-height: 1.6;
      font-size: 14px;
      white-space: pre-wrap;
      margin-bottom: 16px;
    }

    .results-actions {
      display: flex;
      gap: 12px;
    }

    .sample-questions {
      padding: 20px;
    }

    .sample-questions h4 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .questions-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 12px;
    }

    .sample-question {
      text-align: left;
      padding: 12px 16px;
      font-size: 13px;
      line-height: 1.4;
    }

    .qa-interface {
      padding: 20px;
    }

    .question-input {
      width: 100%;
      margin-bottom: 16px;
    }

    .ask-button {
      width: 100%;
    }

    .qa-history h4 {
      margin: 0 0 16px 0;
      padding: 0 8px;
      font-size: 16px;
    }

    .qa-item {
      padding: 20px;
      margin-bottom: 16px;
    }

    .question, .answer {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;
    }

    .question mat-icon {
      color: #2196f3;
      margin-top: 2px;
    }

    .answer mat-icon {
      color: #4caf50;
      margin-top: 2px;
    }

    .qa-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 12px;
    }

    .sessions-section h3 {
      margin: 0 0 20px 0;
      font-size: 18px;
    }

    .sessions-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 16px;
    }

    .session-card {
      background: var(--glass-secondary);
      border-radius: 12px;
      padding: 20px;
      transition: all 0.3s ease;
    }

    .session-card.active {
      border: 2px solid rgba(76, 175, 80, 0.5);
      background: rgba(76, 175, 80, 0.1);
    }

    .session-card:hover {
      transform: translateY(-2px);
    }

    .session-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 12px;
    }

    .session-header mat-icon {
      color: var(--text-primary);
    }

    .session-title {
      flex: 1;
    }

    .session-title h4 {
      margin: 0 0 4px 0;
      font-size: 14px;
      font-weight: 500;
    }

    .session-title p {
      margin: 0;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .session-details {
      display: flex;
      gap: 12px;
      margin-bottom: 12px;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .session-actions {
      display: flex;
      gap: 8px;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .attribution-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 16px;
      }

      .control-row {
        flex-direction: column;
        align-items: stretch;
      }

      .questions-grid {
        grid-template-columns: 1fr;
      }

      .sessions-grid {
        grid-template-columns: 1fr;
      }
    }
  `]
})
export class AttributionComponent implements OnInit {
  chunkList: any[] = [];
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  selectedFile: File | null = null;
  sessionId = '';
  isUploading = false;
  uploadResult: AttributionSession | null = null;

  // Commentary Mode
  commentaryPeriod = '';
  isGeneratingCommentary = false;
  commentaryResponse: AttributionResponse | null = null;
  commentaryPrompt: string = '';

  // Q&A Mode
  currentQuestion = '';
  isAnswering = false;
  qaHistory: AttributionResponse[] = [];

  // UI State
  isDragOver = false;
  activeSessions: AttributionSession[] = [];

  sampleQuestions = [
    'What were the top 3 contributors by total attribution?',
    'Which sectors had positive allocation effect?',
    'Which countries had negative FX but positive selection?',
    'What was the total FX impact?',
    'Show me the rankings by total attribution',
    'What was the portfolio total return vs benchmark?',
    'Which sectors contributed most to active return?',
    'What were the main detractors in the attribution?'
  ];

  constructor(
    private apiService: ApiService,
    private snackBar: MatSnackBar
  ) {}

  ngOnInit() {
    this.loadActiveSessions();
  }

  triggerFileInput() {
    this.fileInput.nativeElement.click();
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files[0]) {
      this.handleFile(input.files[0]);
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
    
    if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
      this.handleFile(event.dataTransfer.files[0]);
    }
  }

  private handleFile(file: File) {
    if (this.isValidFile(file)) {
      this.selectedFile = file;
    } else {
      this.showError('Please select a valid Excel file (.xlsx or .xls)');
    }
  }

  private isValidFile(file: File): boolean {
    const allowedTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
      'application/vnd.ms-excel' // .xls
    ];
    return allowedTypes.includes(file.type);
  }

  clearSelection() {
    this.selectedFile = null;
    this.sessionId = '';
    this.uploadResult = null;
    this.commentaryResponse = null;
    this.qaHistory = [];
    this.commentaryPrompt = '';
  }

  async uploadFile() {
    if (!this.selectedFile) return;

    this.isUploading = true;
    
    try {
      const formData = new FormData();
      formData.append('file', this.selectedFile);
      if (this.sessionId.trim()) {
        formData.append('session_id', this.sessionId.trim());
      }

      const response = await this.apiService.uploadAttributionFile(formData).toPromise();
      
      this.uploadResult = {
        ...response,
        filename: this.selectedFile.name,
        upload_timestamp: new Date().toISOString()
      };

      // Load chunks if available in response
      if (response.chunks && Array.isArray(response.chunks)) {
        this.chunkList = response.chunks.map((chunk: any) => ({ ...chunk, expanded: false }));
        console.log('[Attribution] Chunks loaded:', this.chunkList);
      } else {
        this.chunkList = [];
        console.warn('[Attribution] No chunks found in upload response.');
      }

      // Set commentary period from upload result
      this.commentaryPeriod = this.uploadResult?.period || '';

      this.showSuccess('Attribution file processed successfully!');
      this.loadActiveSessions();

    } catch (error: any) {
      this.showError(error.error?.detail || 'Failed to process attribution file');
    } finally {
      this.isUploading = false;
    }
  }

  async generateCommentary() {
    if (!this.uploadResult) return;

    this.isGeneratingCommentary = true;
    try {
      const formData = new FormData();
      formData.append('session_id', this.uploadResult.session_id);
      if (this.commentaryPeriod.trim()) {
        formData.append('period', this.commentaryPeriod.trim());
      }
      // Don't pass context - let backend retrieve from Qdrant
      // formData.append('context', JSON.stringify(this.chunkList));

      const response = await this.apiService.generateAttributionCommentary(formData).toPromise();
      console.log('[Attribution] Commentary response:', response);
      this.commentaryResponse = response;
      this.commentaryPrompt = response.prompt || '';
      if (this.commentaryPrompt) {
        console.log('[Attribution] Prompt sent to LLM:', this.commentaryPrompt);
      } else {
        console.warn('[Attribution] No prompt found in commentary response.');
      }
    } catch (error: any) {
      this.showError(error.error?.detail || 'Failed to generate commentary');
    } finally {
      this.isGeneratingCommentary = false;
    }
  }

  setQuestion(question: string) {
    this.currentQuestion = question;
  }

  async askQuestion() {
    if (!this.uploadResult || !this.currentQuestion.trim()) return;

    this.isAnswering = true;
    try {
      const formData = new FormData();
      formData.append('session_id', this.uploadResult.session_id);
      formData.append('question', this.currentQuestion.trim());
      formData.append('mode', 'qa');
      // Don't pass context - let backend retrieve from Qdrant
      // formData.append('context', JSON.stringify(this.chunkList));

      const response = await this.apiService.askAttributionQuestion(formData).toPromise();
      // Add to history
      this.qaHistory.unshift({
        ...response,
        question: this.currentQuestion.trim()
      });
      // Clear current question
      this.currentQuestion = '';
    } catch (error: any) {
      this.showError(error.error?.detail || 'Failed to answer question');
    } finally {
      this.isAnswering = false;
    }
  }

  formatCommentary(commentary: string): string {
    // Convert markdown-like formatting to HTML
    return commentary
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>')
      .replace(/^### (.*$)/gm, '<h3>$1</h3>')
      .replace(/^## (.*$)/gm, '<h2>$1</h2>')
      .replace(/^# (.*$)/gm, '<h1>$1</h1>');
  }

  copyToClipboard(text: string) {
    navigator.clipboard.writeText(text).then(() => {
      this.showSuccess('Copied to clipboard');
    }).catch(() => {
      this.showError('Failed to copy to clipboard');
    });
  }

  trackByIndex(index: number, item: any): number {
    return index;
  }

  async loadActiveSessions() {
    try {
      // This would need to be implemented in the API service
      // For now, we'll maintain local session tracking
      this.activeSessions = this.uploadResult ? [this.uploadResult] : [];
    } catch (error) {
      console.error('Failed to load active sessions:', error);
    }
  }

  async clearSession(sessionId: string) {
    if (confirm('Are you sure you want to clear this attribution session?')) {
      try {
        await this.apiService.clearAttributionSession(sessionId).toPromise();
        this.showSuccess('Session cleared successfully');
        this.loadActiveSessions();
        
        if (this.uploadResult?.session_id === sessionId) {
          this.uploadResult = null;
          this.commentaryResponse = null;
          this.qaHistory = [];
        }
      } catch (error: any) {
        this.showError(error.error?.detail || 'Failed to clear session');
      }
    }
  }

  switchToSession(session: AttributionSession) {
  this.chunkList = session.chunks || [];
    this.uploadResult = session;
    this.commentaryPeriod = session.period;
    this.commentaryResponse = null;
    this.qaHistory = [];
    this.commentaryPrompt = '';
  }

  formatDate(dateString: string): string {
    return new Date(dateString).toLocaleDateString();
  }

  private showSuccess(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 5000,
      panelClass: ['success-snackbar']
    });
  }

  private showError(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 5000,
      panelClass: ['error-snackbar']
    });
  }
}