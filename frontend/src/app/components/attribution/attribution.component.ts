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
import { MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';

import { ApiService } from '../../services/api.service';
import { ChatSettingsDialogComponent } from '../chat/chat-settings-dialog.component';

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
  prompt?: string;
  error?: string;
}

interface CollectionInfo {
  session_id: string;
  collection_name: string;
  points_count: number;
  vectors_count: number;
  status: string;
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
    MatDividerModule,
    MatTooltipModule,
    MatMenuModule
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
          <button mat-icon-button 
                  class="glass-button"
                  (click)="toggleSettings()"
                  matTooltip="Attribution Settings">
            <mat-icon>tune</mat-icon>
          </button>
          
          <button mat-raised-button 
                  class="glass-button"
                  (click)="triggerFileInput()">
            <mat-icon>upload_file</mat-icon>
            Upload Attribution File
          </button>
        </div>
      </div>

      <!-- Collection Selection Section -->
      <div class="collection-selection glass-card" *ngIf="availableCollections.length > 0">
        <h3>Select Attribution Data</h3>
        <p class="section-description">
          Choose an existing attribution dataset or upload a new one to analyze.
        </p>
        
        <div class="collection-controls">
          <mat-form-field appearance="outline" class="collection-field">
            <mat-label>Attribution Dataset</mat-label>
            <mat-select [(ngModel)]="selectedCollectionId" 
                        (selectionChange)="onCollectionSelectionChange($event.value)">
              <mat-option value="">Select a dataset...</mat-option>
              <mat-option *ngFor="let collection of availableCollections" 
                          [value]="collection.session_id">
                {{ collection.session_id }} 
                <span class="collection-meta">({{ collection.points_count }} data points)</span>
              </mat-option>
            </mat-select>
          </mat-form-field>
          
          <button mat-icon-button 
                  class="glass-button refresh-btn"
                  (click)="refreshCollections()"
                  matTooltip="Refresh collections">
            <mat-icon>refresh</mat-icon>
          </button>
          
          <button mat-icon-button 
                  class="glass-button delete-btn"
                  *ngIf="selectedCollectionId"
                  (click)="deleteSelectedCollection()"
                  matTooltip="Delete selected dataset">
            <mat-icon>delete</mat-icon>
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
              <strong>Session ID:</strong> {{ uploadResult.session_id }}
            </div>
            <div class="result-item">
              <strong>Asset Class:</strong> {{ uploadResult.asset_class }}
            </div>
            <div class="result-item">
              <strong>Attribution Level:</strong> {{ uploadResult.attribution_level }}
            </div>
            <div class="result-item">
              <strong>Period:</strong> {{ uploadResult.period }}
            </div>
            <div class="result-item">
              <strong>Chunks Created:</strong> {{ uploadResult.chunks_created }}
            </div>
            <div class="result-item">
              <strong>Collection:</strong> {{ uploadResult.collection_name }}
            </div>
          </div>
        </div>
      </div>

      <!-- Chunks Viewer Section -->
      <div class="chunks-section glass-card" *ngIf="chunkList && chunkList.length">
        <div class="collapsible-header" (click)="toggleChunks()">
          <div class="header-content">
            <mat-icon class="section-icon">storage</mat-icon>
            <h3>Attribution Chunks ({{ chunkList.length }})</h3>
          </div>
          <mat-icon class="toggle-icon">{{ showChunks ? 'expand_less' : 'expand_more' }}</mat-icon>
        </div>
        
        <div class="collapsible-content" [class.expanded]="showChunks">
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
                           [value]="uploadResult.period">
                  </mat-form-field>
                  
                  <div class="button-group">
                    <button mat-raised-button 
                            color="primary"
                            class="glass-button"
                            [disabled]="isGeneratingCommentary"
                            (click)="generateCommentary()">
                      <mat-icon>auto_awesome</mat-icon>
                      Generate Commentary
                    </button>
                    
                    <button mat-raised-button 
                            class="glass-button docx-button"
                            [disabled]="!commentaryResponse || isGeneratingDocx"
                            (click)="generateDocxFile()">
                      <mat-icon>description</mat-icon>
                      Generate Word .docx
                    </button>
                  </div>
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
                
                <div class="prompt-section" *ngIf="commentaryPrompt">
                  <div class="collapsible-header small" (click)="toggleCommentaryPrompt()">
                    <div class="header-content">
                      <mat-icon class="section-icon small">code</mat-icon>
                      <h5>Prompt Sent to LLM</h5>
                    </div>
                    <mat-icon class="toggle-icon">{{ showCommentaryPrompt ? 'expand_less' : 'expand_more' }}</mat-icon>
                  </div>
                  
                  <div class="collapsible-content" [class.expanded]="showCommentaryPrompt">
                    <div class="prompt-preview-box">
                      <textarea readonly rows="10" style="width:100%;font-size:12px;background:var(--glass-secondary);border:1px solid rgba(255,255,255,0.2);border-radius:6px;padding:12px;color:var(--text-primary);font-family:'Courier New',monospace;">{{ commentaryPrompt }}</textarea>
                    </div>
                  </div>
                </div>
                
                <div class="commentary-content" [innerHTML]="formatCommentary(commentaryResponse.response)">
                </div>
                
                <div class="results-actions">
                  <button mat-button class="glass-button" (click)="copyToClipboard(commentaryResponse.response)">
                    <mat-icon>content_copy</mat-icon>
                    Copy Commentary
                  </button>
                  
                  <button mat-button 
                          class="glass-button"
                          [disabled]="isGeneratingDocx"
                          (click)="generateDocxFile()">
                    <mat-icon>description</mat-icon>
                    {{ isGeneratingDocx ? 'Generating...' : 'Download as Word' }}
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
                <div *ngFor="let qa of qaHistory; let i = index; trackBy: trackByIndex" 
                     class="qa-item glass-card">
                  <div class="question">
                    <mat-icon>help_outline</mat-icon>
                    <strong>Q:</strong> {{ qa.question }}
                  </div>
                  <mat-divider></mat-divider>
                  <div class="answer">
                    <mat-icon>lightbulb</mat-icon>
                    <div class="answer-content">
                      <strong>A:</strong> 
                      <div class="answer-text">{{ getCleanResponse(qa.response) }}</div>
                    </div>
                  </div>
                  
                  <!-- Collapsible Prompt Section for Q&A -->
                  <div class="prompt-section" *ngIf="qa.prompt">
                    <div class="collapsible-header small" (click)="toggleQaPrompt(i)">
                      <div class="header-content">
                        <mat-icon class="section-icon small">code</mat-icon>
                        <span>View Prompt</span>
                      </div>
                      <mat-icon class="toggle-icon">{{ showQaPrompts[i] ? 'expand_less' : 'expand_more' }}</mat-icon>
                    </div>
                    
                    <div class="collapsible-content" [class.expanded]="showQaPrompts[i]">
                      <div class="prompt-preview-box">
                        <textarea readonly rows="6" style="width:100%;font-size:11px;background:var(--glass-secondary);border:1px solid rgba(255,255,255,0.2);border-radius:6px;padding:8px;color:var(--text-primary);font-family:'Courier New',monospace;">{{ qa.prompt }}</textarea>
                      </div>
                    </div>
                  </div>
                  
                  <div class="qa-meta">
                    <span>Context used: {{ qa.context_used || 0 }} chunks</span>
                    <button mat-icon-button (click)="copyToClipboard(getCleanResponse(qa.response))">
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
      align-items: center;
    }

    .collection-selection {
      padding: 24px;
    }

    .collection-selection h3 {
      margin: 0 0 8px 0;
      font-size: 18px;
    }

    .collection-controls {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .collection-field {
      flex: 1;
      min-width: 300px;
    }

    .collection-meta {
      color: var(--text-secondary);
      font-size: 12px;
      font-style: italic;
    }

    .refresh-btn, .delete-btn {
      opacity: 0.7;
      transition: opacity 0.3s ease;
    }

    .refresh-btn:hover {
      opacity: 1;
      color: #4caf50 !important;
    }

    .delete-btn:hover {
      opacity: 1;
      color: #f44336 !important;
    }

    .upload-section, .analysis-section, .sessions-section {
      padding: 24px;
    }

    .button-group {
      display: flex;
      gap: 12px;
      align-items: center;
    }

    .docx-button {
      background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
      color: white !important;
    }

    .docx-button:disabled {
      background: rgba(0, 0, 0, 0.12) !important;
      color: rgba(0, 0, 0, 0.26) !important;
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
      align-items: flex-end;
      flex-wrap: wrap;
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

    /* Collapsible Sections */
    .collapsible-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 20px;
      cursor: pointer;
      transition: all 0.3s ease;
      border-radius: 12px;
      background: var(--glass-accent);
      border: 1px solid rgba(255, 255, 255, 0.1);
      margin-bottom: 12px;
    }

    .collapsible-header:hover {
      background: var(--glass-secondary);
      transform: translateY(-1px);
    }

    .collapsible-header.small {
      padding: 12px 16px;
      margin-bottom: 8px;
    }

    .header-content {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .header-content h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 500;
    }

    .header-content h5 {
      margin: 0;
      font-size: 14px;
      font-weight: 500;
    }

    .header-content span {
      font-size: 14px;
      font-weight: 500;
    }

    .section-icon {
      color: var(--text-primary);
      opacity: 0.8;
    }

    .section-icon.small {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }

    .toggle-icon {
      transition: transform 0.3s ease;
      color: var(--text-secondary);
    }

    .collapsible-content {
      max-height: 0;
      overflow: hidden;
      transition: all 0.3s ease;
      opacity: 0;
    }

    .collapsible-content.expanded {
      max-height: 2000px;
      opacity: 1;
      margin-bottom: 16px;
    }

    .prompt-section {
      margin: 16px 0;
    }

    .prompt-preview-box {
      padding: 0;
    }

    .prompt-preview-box textarea {
      resize: vertical;
      min-height: 100px;
    }

    .answer-content {
      flex: 1;
    }

    .answer-text {
      margin-top: 8px;
      padding: 12px;
      background: var(--glass-secondary);
      border-radius: 8px;
      border-left: 3px solid #4caf50;
      line-height: 1.6;
      white-space: pre-wrap;
    }

    .chunks-section .collapsible-content.expanded {
      max-height: 1000px;
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

      .collapsible-header {
        padding: 14px 16px;
      }

      .collapsible-header.small {
        padding: 10px 12px;
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
  
  // Collapsible sections
  showChunks = false;
  showCommentaryPrompt = false;
  showQaPrompts: { [key: number]: boolean } = {};

  // Collection management
  availableCollections: CollectionInfo[] = [];
  selectedCollectionId = '';
  
  // Document generation
  isGeneratingDocx = false;

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
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit() {
    this.loadActiveSessions();
    this.loadAvailableCollections();
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

  toggleChunks() {
    this.showChunks = !this.showChunks;
  }

  toggleCommentaryPrompt() {
    this.showCommentaryPrompt = !this.showCommentaryPrompt;
  }

  toggleQaPrompt(index: number) {
    this.showQaPrompts[index] = !this.showQaPrompts[index];
  }

  getCleanResponse(response: string): string {
    // Clean up Q&A response - remove JSON formatting and unwanted characters
    if (!response) return 'No response available';
    
    try {
      // Try to parse as JSON in case it's wrapped
      const parsed = JSON.parse(response);
      if (typeof parsed === 'string') {
        return parsed.trim();
      }
      if (parsed.response) {
        return parsed.response.trim();
      }
      if (parsed.answer) {
        return parsed.answer.trim();
      }
    } catch {
      // Not JSON, continue with string cleaning
    }
    
    // Clean up common formatting issues
    return response
      .replace(/^["']|["']$/g, '') // Remove quotes at start/end
      .replace(/\\n/g, '\n')       // Fix escaped newlines
      .replace(/\\"/g, '"')        // Fix escaped quotes
      .replace(/^\s*{\s*"response"\s*:\s*"?|"?\s*}\s*$/g, '') // Remove JSON wrapper
      .replace(/^Response:\s*/i, '') // Remove "Response:" prefix
      .trim();
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

  // Collection management methods
  async loadAvailableCollections() {
    try {
      const response = await this.apiService.getAttributionCollections().toPromise();
      this.availableCollections = response.collections || [];
    } catch (error) {
      console.error('Failed to load collections:', error);
    }
  }

  refreshCollections() {
    this.loadAvailableCollections();
  }

  onCollectionSelectionChange(sessionId: string) {
    this.selectedCollectionId = sessionId;
    if (sessionId) {
      // Load session data for the selected collection
      this.loadSessionData(sessionId);
    }
  }

  async loadSessionData(sessionId: string) {
    try {
      // Set the current session to the selected one
      this.uploadResult = {
        session_id: sessionId,
        collection_name: `attr_session_${sessionId}`,
        chunks_created: 0,
        period: '',
        asset_class: '',
        attribution_level: '',
        upload_timestamp: new Date().toISOString(),
        filename: `Session ${sessionId}`
      };
      
      this.showSuccess(`Selected attribution session: ${sessionId}`);
    } catch (error) {
      this.showError('Failed to load session data');
    }
  }

  async deleteSelectedCollection() {
    if (!this.selectedCollectionId) return;
    
    if (confirm(`Are you sure you want to delete the attribution session "${this.selectedCollectionId}"? This action cannot be undone.`)) {
      try {
        await this.apiService.clearAttributionSession(this.selectedCollectionId).toPromise();
        this.showSuccess('Attribution session deleted successfully');
        this.selectedCollectionId = '';
        this.uploadResult = null;
        this.commentaryResponse = null;
        this.qaHistory = [];
        this.loadAvailableCollections();
      } catch (error: any) {
        this.showError(error.error?.detail || 'Failed to delete session');
      }
    }
  }

  // Chat settings functionality
  toggleSettings() {
    const dialogRef = this.dialog.open(ChatSettingsDialogComponent, {
      width: '700px',
      maxWidth: '95vw',
      maxHeight: '90vh',
      data: { 
        sessionId: this.uploadResult?.session_id,
        documentType: 'performance_attribution'
      },
      panelClass: 'chat-settings-dialog-panel'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result?.saved) {
        console.log('Attribution settings updated:', result.settings);
        this.showSuccess('Attribution settings have been updated for this session');
      }
    });
  }

  // Document generation functionality
  async generateDocxFile() {
    if (!this.commentaryResponse) {
      this.showError('No commentary available to export');
      return;
    }

    this.isGeneratingDocx = true;
    
    try {
      // Simple client-side Word document generation
      const content = this.commentaryResponse.response;
      const htmlContent = this.formatCommentary(content);
      
      // Create a blob with HTML content that Word can open
      const docxContent = `
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
          <title>Performance Attribution Commentary</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1, h2, h3 { color: #333; }
            .header { text-align: center; margin-bottom: 30px; }
            .meta { color: #666; font-size: 12px; margin-bottom: 20px; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>Performance Attribution Commentary</h1>
            <div class="meta">
              Generated on ${new Date().toLocaleDateString()}<br/>
              Session: ${this.commentaryResponse.session_id}
            </div>
          </div>
          <div class="content">
            ${htmlContent}
          </div>
        </body>
        </html>
      `;
      
      const blob = new Blob([docxContent], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `Attribution_Commentary_${this.commentaryResponse.session_id}_${new Date().toISOString().split('T')[0]}.doc`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      this.showSuccess('Word document downloaded successfully');
      
    } catch (error) {
      console.error('Failed to generate Word document:', error);
      this.showError('Failed to generate Word document');
    } finally {
      this.isGeneratingDocx = false;
    }
  }
}