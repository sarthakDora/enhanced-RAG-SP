import { Component, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { DocumentType, DocumentListItem, DocumentStats } from '../../models/document.model';

interface UploadFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

interface AttributionSession {
  session_id: string;
  collection_name: string;
  chunks_created: number;
  period: string;
  asset_class: string;
  attribution_level: string;
  upload_timestamp: string;
  filename: string;
}

interface AttributionResponse {
  mode: 'qa' | 'commentary';
  response: string;
  session_id: string;
  question?: string;
  context_used?: number;
}

interface CollectionInfo {
  session_id: string;
  collection_name: string;
  points_count: number;
  vectors_count: number;
  status: string;
}

@Component({
  selector: 'app-documents',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatChipsModule,
    MatProgressBarModule,
    MatSelectModule,
    MatInputModule,
    MatTabsModule,
    MatDividerModule,
    MatTooltipModule
  ],
  template: `
    <div class="documents-container fade-in">
      <!-- Header -->
      <div class="documents-header glass-card">
        <div>
          <h2 class="gradient-text">Document Management</h2>
          <p class="text-muted">Upload and manage your financial documents</p>
        </div>
        
        <div class="header-actions">
          <button mat-raised-button 
                  class="glass-button"
                  (click)="triggerFileInput()">
            <mat-icon>upload_file</mat-icon>
            Upload Documents
          </button>
        </div>
      </div>

      <!-- Upload Area -->
      <div class="upload-section">
        <!-- Drag & Drop Area -->
        <div class="upload-area glass-card"
             [class.dragover]="isDragOver"
             (dragover)="onDragOver($event)"
             (dragleave)="onDragLeave($event)"
             (drop)="onDrop($event)"
             (click)="triggerFileInput()">
          
          <input #fileInput 
                 type="file" 
                 multiple 
                 accept=".pdf,.docx,.txt,.xlsx,.xls"
                 (change)="onFileSelected($event)"
                 style="display: none;">
          
          <div class="upload-content">
            <mat-icon class="upload-icon">cloud_upload</mat-icon>
            <h3>Drag & Drop Files Here</h3>
            <p>Or click to browse files</p>
            <p class="file-info">Supported formats: PDF, DOCX, TXT, XLSX, XLS (Max 1GB)</p>
          </div>
        </div>

        <!-- Upload Configuration -->
        <div class="upload-config glass-card" *ngIf="selectedFiles.length > 0">
          <h4>Upload Configuration</h4>
          
          <!-- Attribution File Detection -->
          <div class="attribution-detection" *ngIf="hasAttributionFiles">
            <div class="detection-notice">
              <mat-icon>info</mat-icon>
              <div>
                <strong>Attribution Files Detected</strong>
                <p>Excel files detected that may contain performance attribution data. 
                   Consider using the <a routerLink="/attribution">Attribution Analysis</a> feature for specialized processing.</p>
              </div>
              <button mat-button 
                      class="glass-button"
                      routerLink="/attribution">
                <mat-icon>account_balance</mat-icon>
                Go to Attribution
              </button>
            </div>
          </div>
          
          <div class="config-row">
            <mat-form-field appearance="outline">
              <mat-label>Document Type</mat-label>
              <mat-select [(value)]="selectedDocumentType">
                <mat-option *ngFor="let type of documentTypes" [value]="type.value">
                  {{ type.label }}
                </mat-option>
              </mat-select>
            </mat-form-field>
            
            <mat-form-field appearance="outline">
              <mat-label>Tags (comma separated)</mat-label>
              <input matInput [(ngModel)]="tags" placeholder="e.g., Q4-2023, earnings, report">
            </mat-form-field>
          </div>

          <div class="upload-actions">
            <button mat-raised-button 
                    color="primary"
                    class="glass-button"
                    [disabled]="isUploading"
                    (click)="uploadFiles()">
              <mat-icon>upload</mat-icon>
              {{ isPerformanceAttribution ? 'Process Attribution File' : 'Upload' }} {{ selectedFiles.length }} File(s)
            </button>
            
            <button mat-button 
                    class="glass-button"
                    (click)="clearSelection()">
              <mat-icon>clear</mat-icon>
              Clear
            </button>
          </div>
        </div>

        <!-- Attribution Configuration (when Performance Attribution is selected) -->
        <div class="attribution-config glass-card" *ngIf="isPerformanceAttribution && selectedFiles.length > 0">
          <h4>Attribution Configuration</h4>
          <p class="section-description">
            Configure performance attribution processing for Excel files with sector or country-level data.
          </p>
          
          <div class="config-row">
            <mat-form-field appearance="outline">
              <mat-label>Session ID (optional)</mat-label>
              <input matInput [(ngModel)]="attributionSessionId" 
                     placeholder="Auto-generated if empty">
            </mat-form-field>
          </div>
        </div>

        <!-- Upload Progress -->
        <div class="upload-progress glass-card" *ngIf="uploadFilesList.length > 0">
          <h4>Upload Progress</h4>
          
          <div *ngFor="let uploadFile of uploadFilesList" class="upload-file-item">
            <div class="file-info">
              <mat-icon>{{ getFileIcon(uploadFile.file.name) }}</mat-icon>
              <div class="file-details">
                <span class="file-name">{{ uploadFile.file.name }}</span>
                <span class="file-size">{{ formatFileSize(uploadFile.file.size) }}</span>
              </div>
              <div class="file-status">
                <mat-icon [class]="uploadFile.status">
                  {{ getUploadStatusIcon(uploadFile.status) }}
                </mat-icon>
              </div>
            </div>
            
            <mat-progress-bar 
              *ngIf="uploadFile.status === 'uploading'"
              [value]="uploadFile.progress"
              mode="determinate">
            </mat-progress-bar>
            
            <div *ngIf="uploadFile.error" class="error-message">
              {{ uploadFile.error }}
            </div>
          </div>
        </div>

        <!-- Attribution Results (when Performance Attribution is processed) -->
        <div class="attribution-results glass-card" *ngIf="attributionResult">
          <h4>✅ Attribution File Processed Successfully</h4>
          <div class="result-grid">
            <div class="result-item">
              <strong>Session ID:</strong> {{ attributionResult.session_id }}
            </div>
            <div class="result-item">
              <strong>Asset Class:</strong> {{ attributionResult.asset_class }}
            </div>
            <div class="result-item">
              <strong>Attribution Level:</strong> {{ attributionResult.attribution_level }}
            </div>
            <div class="result-item">
              <strong>Period:</strong> {{ attributionResult.period }}
            </div>
            <div class="result-item">
              <strong>Chunks Created:</strong> {{ attributionResult.chunks_created }}
            </div>
            <div class="result-item">
              <strong>Collection:</strong> {{ attributionResult.collection_name }}
            </div>
          </div>
        </div>

        <!-- Attribution Analysis Section -->
        <div class="attribution-analysis" *ngIf="attributionResult">
          <mat-tab-group>
            <!-- Commentary Mode Tab -->
            <mat-tab label="Commentary Mode">
              <div class="tab-content">
                <div class="mode-description glass-card">
                  <mat-icon>article</mat-icon>
                  <div>
                    <h4>Professional Attribution Commentary</h4>
                    <p>Generate institutional-grade performance attribution commentary using the uploaded data.</p>
                  </div>
                </div>

                <div class="commentary-controls glass-card">
                  <div class="control-row">
                    <mat-form-field appearance="outline">
                      <mat-label>Period (optional)</mat-label>
                      <input matInput [(ngModel)]="commentaryPeriod" 
                             placeholder="e.g., Q2 2025"
                             [value]="attributionResult.period">
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
                    </div>
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
                    <p>Ask specific questions about the attribution data. Answers are strictly based on the uploaded document context.</p>
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
      </div>

      <!-- Documents Stats -->
      <div class="stats-section" *ngIf="stats">
        <div class="stats-grid">
          <div class="stat-card glass-card">
            <mat-icon>description</mat-icon>
            <div class="stat-content">
              <h3>{{ stats.total_documents }}</h3>
              <p>Total Documents</p>
            </div>
          </div>
          
          <div class="stat-card glass-card">
            <mat-icon>analytics</mat-icon>
            <div class="stat-content">
              <h3>{{ stats.documents_with_financial_data }}</h3>
              <p>Financial Documents</p>
            </div>
          </div>
          
          <div class="stat-card glass-card">
            <mat-icon>view_module</mat-icon>
            <div class="stat-content">
              <h3>{{ stats.total_chunks }}</h3>
              <p>Total Chunks</p>
            </div>
          </div>
          
          <div class="stat-card glass-card">
            <mat-icon>speed</mat-icon>
            <div class="stat-content">
              <h3>{{ stats.average_chunks_per_document.toFixed(1) }}</h3>
              <p>Avg Chunks/Doc</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Attribution Collections List -->
      <div class="collections-list glass-card" *ngIf="attributionCollections.length > 0">
        <div class="list-header">
          <h3>Attribution Collections</h3>
          <button mat-icon-button 
                  class="glass-button"
                  (click)="refreshCollections()"
                  matTooltip="Refresh collections">
            <mat-icon>refresh</mat-icon>
          </button>
        </div>

        <div class="collections-grid">
          <div *ngFor="let collection of attributionCollections" 
               class="collection-card glass-card">
            
            <div class="collection-header">
              <mat-icon class="collection-icon">analytics</mat-icon>
              <div class="collection-title">
                <h4>{{ collection.session_id }}</h4>
                <p class="collection-type">Attribution Dataset</p>
              </div>
              <button mat-icon-button 
                      class="delete-button"
                      (click)="deleteCollection(collection, $event)"
                      matTooltip="Delete collection">
                <mat-icon>delete</mat-icon>
              </button>
            </div>

            <div class="collection-meta">
              <div class="meta-item">
                <mat-icon>storage</mat-icon>
                <span>{{ collection.points_count }} data points</span>
              </div>
              
              <div class="meta-item">
                <mat-icon>view_module</mat-icon>
                <span>{{ collection.vectors_count }} vectors</span>
              </div>
              
              <div class="meta-item" [class]="getStatusClass(collection.status)">
                <mat-icon>{{ getStatusIcon(collection.status) }}</mat-icon>
                <span>{{ collection.status }}</span>
              </div>
            </div>

            <div class="collection-footer">
              <span class="collection-name">{{ collection.collection_name }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Documents List -->
      <div class="documents-list glass-card">
        <div class="list-header">
          <h3>Uploaded Documents</h3>
          <button mat-icon-button 
                  class="glass-button"
                  (click)="refreshDocuments()">
            <mat-icon>refresh</mat-icon>
          </button>
        </div>

        <div class="documents-grid" *ngIf="documents.length > 0; else noDocuments">
          <div *ngFor="let doc of documents" 
               class="document-card glass-card"
               (click)="openDocument(doc)">
            
            <div class="document-header">
              <mat-icon class="doc-type-icon">
                {{ getDocumentTypeIcon(doc.document_type) }}
              </mat-icon>
              <div class="document-title">
                <h4>{{ doc.filename }}</h4>
                <p class="document-type">{{ getDocumentTypeLabel(doc.document_type) }}</p>
              </div>
              <button mat-icon-button 
                      class="delete-button"
                      (click)="deleteDocument(doc, $event)">
                <mat-icon>delete</mat-icon>
              </button>
            </div>

            <div class="document-meta">
              <div class="meta-item">
                <mat-icon>pages</mat-icon>
                <span>{{ doc.total_pages }} pages</span>
              </div>
              
              <div class="meta-item">
                <mat-icon>view_module</mat-icon>
                <span>{{ doc.total_chunks }} chunks</span>
              </div>
              
              <div class="meta-item" *ngIf="doc.has_financial_data">
                <mat-icon>attach_money</mat-icon>
                <span>Financial Data</span>
              </div>
            </div>

            <div class="document-tags" *ngIf="doc.tags.length > 0">
              <mat-chip-set>
                <mat-chip *ngFor="let tag of doc.tags.slice(0, 3)">
                  {{ tag }}
                </mat-chip>
                <mat-chip *ngIf="doc.tags.length > 3">
                  +{{ doc.tags.length - 3 }}
                </mat-chip>
              </mat-chip-set>
            </div>

            <div class="document-footer">
              <div class="confidence-indicator" [class]="getConfidenceClass(doc.confidence_score)">
                <mat-icon>{{ getConfidenceIcon(doc.confidence_score) }}</mat-icon>
                <span>{{ (doc.confidence_score * 100).toFixed(0) }}%</span>
              </div>
              
              <span class="upload-date">
                {{ formatDate(doc.upload_timestamp) }}
              </span>
            </div>
          </div>
        </div>

        <ng-template #noDocuments>
          <div class="no-documents">
            <mat-icon>description</mat-icon>
            <h3>No Documents Yet</h3>
            <p>Upload your first financial document to get started</p>
            <button mat-raised-button 
                    color="primary"
                    class="glass-button"
                    (click)="triggerFileInput()">
              <mat-icon>upload_file</mat-icon>
              Upload Document
            </button>
          </div>
        </ng-template>
      </div>
    </div>
  `,
  styles: [`
    .documents-container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    .documents-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 24px;
    }

    .documents-header h2 {
      margin: 0;
      font-size: 24px;
    }

    .documents-header p {
      margin: 4px 0 0 0;
      font-size: 14px;
    }

    .header-actions {
      display: flex;
      gap: 12px;
    }

    .upload-section {
      display: flex;
      flex-direction: column;
      gap: 16px;
    }

    .upload-area {
      padding: 48px 24px;
      text-align: center;
      cursor: pointer;
      transition: all 0.3s ease;
      border: 2px dashed rgba(255, 255, 255, 0.3);
      border-radius: 16px;
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

    .upload-content h3 {
      margin: 0 0 8px 0;
      font-size: 20px;
    }

    .upload-content p {
      margin: 4px 0;
      color: var(--text-secondary);
    }

    .file-info {
      font-size: 12px;
      color: var(--text-muted);
    }

    .upload-config {
      padding: 24px;
    }

    .upload-config h4 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .attribution-detection {
      margin-bottom: 20px;
    }

    .detection-notice {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 16px;
      background: rgba(33, 150, 243, 0.1);
      border: 1px solid rgba(33, 150, 243, 0.3);
      border-radius: 8px;
    }

    .detection-notice mat-icon {
      color: #2196f3;
      margin-top: 2px;
    }

    .detection-notice > div {
      flex: 1;
    }

    .detection-notice strong {
      display: block;
      margin-bottom: 4px;
      color: #2196f3;
    }

    .detection-notice p {
      margin: 0;
      font-size: 14px;
      color: var(--text-secondary);
      line-height: 1.4;
    }

    .detection-notice a {
      color: #2196f3;
      text-decoration: none;
    }

    .detection-notice a:hover {
      text-decoration: underline;
    }

    .config-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 16px;
    }

    .upload-actions {
      display: flex;
      gap: 12px;
    }

    .upload-progress {
      padding: 24px;
    }

    .upload-progress h4 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .upload-file-item {
      margin-bottom: 16px;
      padding: 12px;
      background: var(--glass-secondary);
      border-radius: 8px;
    }

    .upload-file-item .file-info {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }

    .file-details {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .file-name {
      font-weight: 500;
      font-size: 14px;
    }

    .file-size {
      font-size: 12px;
      color: var(--text-muted);
    }

    .file-status mat-icon.completed {
      color: #4caf50;
    }

    .file-status mat-icon.error {
      color: #f44336;
    }

    .file-status mat-icon.uploading {
      color: #2196f3;
    }

    .error-message {
      color: #f44336;
      font-size: 12px;
      margin-top: 4px;
    }

    .stats-section {
      margin: 24px 0;
    }

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }

    .stat-card {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 20px;
      transition: all 0.3s ease;
    }

    .stat-card:hover {
      transform: translateY(-2px);
    }

    .stat-card mat-icon {
      font-size: 32px;
      width: 32px;
      height: 32px;
      color: var(--text-primary);
    }

    .stat-content h3 {
      margin: 0;
      font-size: 24px;
      font-weight: 600;
    }

    .stat-content p {
      margin: 4px 0 0 0;
      color: var(--text-secondary);
      font-size: 14px;
    }

    .collections-list {
      padding: 24px;
      margin-bottom: 24px;
    }

    .collections-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
    }

    .collection-card {
      padding: 20px;
      cursor: pointer;
      transition: all 0.3s ease;
      border-radius: 12px;
      border-left: 4px solid #667eea;
    }

    .collection-card:hover {
      transform: translateY(-2px);
      background: var(--glass-accent) !important;
    }

    .collection-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }

    .collection-icon {
      color: #667eea;
      margin-top: 4px;
    }

    .collection-title {
      flex: 1;
    }

    .collection-title h4 {
      margin: 0 0 4px 0;
      font-size: 16px;
      font-weight: 500;
      line-height: 1.3;
    }

    .collection-type {
      margin: 0;
      font-size: 12px;
      color: var(--text-secondary);
      text-transform: capitalize;
    }

    .collection-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }

    .collection-footer {
      font-size: 11px;
      color: var(--text-muted);
      font-family: monospace;
    }

    .collection-name {
      background: var(--glass-secondary);
      padding: 4px 8px;
      border-radius: 4px;
    }

    .status-active {
      color: #4caf50;
    }

    .status-error {
      color: #f44336;
    }

    .status-unknown {
      color: #ff9800;
    }

    .documents-list {
      padding: 24px;
    }

    .list-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
    }

    .list-header h3 {
      margin: 0;
      font-size: 18px;
    }

    .documents-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 16px;
    }

    .document-card {
      padding: 20px;
      cursor: pointer;
      transition: all 0.3s ease;
      border-radius: 12px;
    }

    .document-card:hover {
      transform: translateY(-2px);
      background: var(--glass-accent) !important;
    }

    .document-header {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 16px;
    }

    .doc-type-icon {
      color: var(--text-primary);
      margin-top: 4px;
    }

    .document-title {
      flex: 1;
    }

    .document-title h4 {
      margin: 0 0 4px 0;
      font-size: 16px;
      font-weight: 500;
      line-height: 1.3;
    }

    .document-type {
      margin: 0;
      font-size: 12px;
      color: var(--text-secondary);
      text-transform: capitalize;
    }

    .delete-button {
      opacity: 0.6;
      transition: opacity 0.3s ease;
    }

    .delete-button:hover {
      opacity: 1;
      color: #f44336;
    }

    .document-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }

    .meta-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      color: var(--text-secondary);
    }

    .meta-item mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .document-tags {
      margin-bottom: 12px;
    }

    .document-tags mat-chip {
      font-size: 11px;
      height: 24px;
    }

    .document-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .confidence-indicator {
      display: flex;
      align-items: center;
      gap: 4px;
      padding: 4px 8px;
      border-radius: 12px;
      font-size: 12px;
    }

    .confidence-indicator.high {
      background: rgba(76, 175, 80, 0.2);
      color: #4caf50;
    }

    .confidence-indicator.medium {
      background: rgba(255, 193, 7, 0.2);
      color: #ffc107;
    }

    .confidence-indicator.low {
      background: rgba(244, 67, 54, 0.2);
      color: #f44336;
    }

    .confidence-indicator mat-icon {
      font-size: 14px;
      width: 14px;
      height: 14px;
    }

    .upload-date {
      font-size: 12px;
      color: var(--text-muted);
    }

    .no-documents {
      text-align: center;
      padding: 48px 24px;
    }

    .no-documents mat-icon {
      font-size: 64px;
      width: 64px;
      height: 64px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }

    .no-documents h3 {
      margin: 0 0 8px 0;
      color: var(--text-secondary);
    }

    .no-documents p {
      margin: 0 0 24px 0;
      color: var(--text-muted);
    }

    /* Attribution styles */
    .attribution-config {
      padding: 24px;
    }

    .attribution-config h4 {
      margin: 0 0 16px 0;
      font-size: 16px;
    }

    .section-description {
      color: var(--text-secondary);
      margin: 0 0 20px 0;
      font-size: 14px;
    }

    .attribution-results {
      background: rgba(76, 175, 80, 0.1);
      border: 1px solid rgba(76, 175, 80, 0.3);
      padding: 20px;
      border-radius: 12px;
      margin-top: 20px;
    }

    .attribution-results h4 {
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

    .attribution-analysis {
      margin-top: 24px;
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

    /* Responsive Design */
    @media (max-width: 768px) {
      .documents-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 16px;
      }

      .config-row {
        grid-template-columns: 1fr;
      }

      .control-row {
        flex-direction: column;
        align-items: stretch;
      }

      .questions-grid {
        grid-template-columns: 1fr;
      }

      .stats-grid {
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      }

      .documents-grid {
        grid-template-columns: 1fr;
      }

      .collections-grid {
        grid-template-columns: 1fr;
      }

      .upload-actions {
        flex-direction: column;
      }
    }
  `]
})
export class DocumentsComponent implements OnInit, OnDestroy {
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  documents: DocumentListItem[] = [];
  stats: DocumentStats | null = null;
  selectedFiles: File[] = [];
  uploadFilesList: UploadFile[] = [];
  selectedDocumentType: DocumentType = DocumentType.OTHER;
  tags = '';
  isDragOver = false;
  isUploading = false;
  hasAttributionFiles = false;
  
  // Collections management
  attributionCollections: CollectionInfo[] = [];
  
  // Attribution-specific properties
  attributionResult: AttributionSession | null = null;
  attributionSessionId = '';
  commentaryPeriod = '';
  isGeneratingCommentary = false;
  commentaryResponse: AttributionResponse | null = null;
  currentQuestion = '';
  isAnswering = false;
  qaHistory: AttributionResponse[] = [];
  sampleQuestions = [
    'What were the top 3 contributors by total attribution?',
    'Which sectors had positive allocation effect?',
    'Which countries had negative FX but positive selection?',
    'What was the total FX impact?',
    'Show me the rankings by total attribution',
    'What was the portfolio total return vs benchmark?'
  ];

  documentTypes = [
    { value: DocumentType.FINANCIAL_REPORT, label: 'Financial Report' },
    { value: DocumentType.LEGAL_CONTRACT, label: 'Legal Contract' },
    { value: DocumentType.COMPLIANCE_REPORT, label: 'Compliance Report' },
    { value: DocumentType.MARKET_ANALYSIS, label: 'Market Analysis' },
    { value: DocumentType.PERFORMANCE_ATTRIBUTION, label: 'Performance Attribution' },
    { value: DocumentType.OTHER, label: 'Other' }
  ];

  private subscriptions: Subscription[] = [];

  constructor(
    private apiService: ApiService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit() {
    this.loadDocuments();
    this.loadStats();
    this.loadAttributionCollections();
    
    // Subscribe to documents updates
    const docUpdateSub = this.apiService.documentsUpdated$.subscribe(() => {
      this.refreshDocuments();
    });
    this.subscriptions.push(docUpdateSub);
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  get isPerformanceAttribution(): boolean {
    return this.selectedDocumentType === DocumentType.PERFORMANCE_ATTRIBUTION;
  }

  triggerFileInput() {
    this.fileInput.nativeElement.click();
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      this.handleFiles(Array.from(input.files));
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
    
    if (event.dataTransfer?.files) {
      this.handleFiles(Array.from(event.dataTransfer.files));
    }
  }

  private handleFiles(files: File[]) {
    const validFiles = files.filter(file => this.isValidFile(file));
    this.selectedFiles = [...this.selectedFiles, ...validFiles];
    
    // Check for attribution files
    this.checkForAttributionFiles();
    
    if (validFiles.length !== files.length) {
      this.showError('Some files were rejected. Only PDF, DOCX, TXT, XLSX, and XLS files under 1GB are allowed.');
    }
  }

  private isValidFile(file: File): boolean {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
      'application/vnd.ms-excel', // .xls
      'text/plain'
    ];
    const maxSize = 1024 * 1024 * 1024; // 1GB
    return allowedTypes.includes(file.type) && file.size <= maxSize;
  }

  clearSelection() {
    this.selectedFiles = [];
    this.uploadFilesList = [];
    this.tags = '';
    this.hasAttributionFiles = false;
    this.attributionResult = null;
    this.attributionSessionId = '';
    this.commentaryPeriod = '';
    this.commentaryResponse = null;
    this.currentQuestion = '';
    this.qaHistory = [];
  }

  private checkForAttributionFiles() {
    this.hasAttributionFiles = this.selectedFiles.some(file => 
      file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || // .xlsx
      file.type === 'application/vnd.ms-excel' // .xls
    );
  }

  async uploadFiles() {
    if (this.selectedFiles.length === 0) return;

    this.isUploading = true;
    
    // Handle Performance Attribution processing
    if (this.isPerformanceAttribution) {
      await this.processAttributionFiles();
      return;
    }

    // Handle regular document upload
    this.uploadFilesList = this.selectedFiles.map(file => ({
      file,
      progress: 0,
      status: 'uploading' as const
    }));

    try {
      const response = await this.apiService.uploadDocuments(
        this.selectedFiles,
        this.selectedDocumentType,
        this.tags
      ).toPromise();

      // Update upload status
      response.documents.forEach((doc: any, index: number) => {
        if (this.uploadFilesList[index]) {
          this.uploadFilesList[index].status = doc.status === 'processed' ? 'completed' : 'error';
          this.uploadFilesList[index].progress = 100;
          if (doc.error) {
            this.uploadFilesList[index].error = doc.error;
          }
        }
      });

      const successCount = response.total_successful;
      this.showSuccess(`Successfully uploaded ${successCount} of ${this.selectedFiles.length} documents`);

      // Refresh data
      await this.loadDocuments();
      await this.loadStats();

      // Clear after delay
      setTimeout(() => {
        this.clearSelection();
      }, 3000);

    } catch (error) {
      this.uploadFilesList.forEach(uploadFile => {
        if (uploadFile.status === 'uploading') {
          uploadFile.status = 'error';
          uploadFile.error = 'Upload failed';
        }
      });
      this.showError('Upload failed. Please try again.');
    } finally {
      this.isUploading = false;
    }
  }

  async loadDocuments() {
    try {
      const response = await this.apiService.getDocuments().toPromise();
      this.documents = response.documents;
    } catch (error) {
      this.showError('Failed to load documents');
    }
  }

  async loadStats() {
    try {
      const response = await this.apiService.getDocumentStats().toPromise();
      this.stats = response;
    } catch (error) {
      console.error('Failed to load stats:', error);
    }
  }

  refreshDocuments() {
    this.loadDocuments();
    this.loadStats();
  }

  openDocument(doc: DocumentListItem) {
    // Implement document viewer
    console.log('Opening document:', doc);
  }

  async deleteDocument(doc: DocumentListItem, event: Event) {
    event.stopPropagation();
    
    if (confirm(`Are you sure you want to delete "${doc.filename}"?`)) {
      try {
        await this.apiService.deleteDocument(doc.document_id).toPromise();
        this.showSuccess('Document deleted successfully');
        this.loadDocuments();
        this.loadStats();
      } catch (error) {
        this.showError('Failed to delete document');
      }
    }
  }

  getFileIcon(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase();
    
    switch (extension) {
      case 'pdf':
        return 'picture_as_pdf';
      case 'docx':
      case 'doc':
        return 'description';
      case 'txt':
        return 'text_snippet';
      case 'xlsx':
      case 'xls':
        return 'table_view';
      default:
        return 'insert_drive_file';
    }
  }

  getUploadStatusIcon(status: string): string {
    switch (status) {
      case 'completed':
        return 'check_circle';
      case 'error':
        return 'error';
      case 'uploading':
        return 'hourglass_empty';
      default:
        return 'radio_button_unchecked';
    }
  }

  getStatusIcon(status: string): string {
    switch (status) {
      case 'active':
        return 'check_circle';
      case 'error':
        return 'error';
      default:
        return 'help_outline';
    }
  }

  getDocumentTypeIcon(type: string): string {
    const iconMap: { [key: string]: string } = {
      'financial_report': 'assessment',
      'legal_contract': 'gavel',
      'compliance_report': 'verified_user',
      'market_analysis': 'trending_up',
      'performance_attribution': 'analytics',
      'other': 'description'
    };
    return iconMap[type] || 'description';
  }

  getDocumentTypeLabel(type: string): string {
    const typeObj = this.documentTypes.find(t => t.value === type);
    return typeObj ? typeObj.label : 'Other';
  }

  getConfidenceClass(score: number): string {
    if (score >= 0.8) return 'high';
    if (score >= 0.6) return 'medium';
    return 'low';
  }

  getConfidenceIcon(score: number): string {
    if (score >= 0.8) return 'check_circle';
    if (score >= 0.6) return 'warning';
    return 'error';
  }

  formatFileSize(bytes: number): string {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
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

  // Attribution-specific methods
  async processAttributionFiles() {
    if (this.selectedFiles.length === 0) return;

    this.isUploading = true;
    
    try {
      // Process only the first Excel file for attribution
      const excelFile = this.selectedFiles.find(file => 
        file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || 
        file.type === 'application/vnd.ms-excel'
      );
      
      if (!excelFile) {
        this.showError('No Excel files found for attribution processing');
        return;
      }

      const formData = new FormData();
      formData.append('file', excelFile);
      if (this.attributionSessionId.trim()) {
        formData.append('session_id', this.attributionSessionId.trim());
      }

      const response = await this.apiService.uploadAttributionFile(formData).toPromise();
      
      this.attributionResult = {
        ...response,
        filename: excelFile.name,
        upload_timestamp: new Date().toISOString()
      };

      // Set commentary period from upload result
      this.commentaryPeriod = this.attributionResult?.period || '';

      this.showSuccess('Attribution file processed successfully!');
      
      // Clear file selection after successful processing
      this.selectedFiles = [];

    } catch (error: any) {
      this.showError(error.error?.detail || 'Failed to process attribution file');
    } finally {
      this.isUploading = false;
    }
  }

  async generateCommentary() {
    if (!this.attributionResult) return;

    this.isGeneratingCommentary = true;
    
    try {
      const formData = new FormData();
      formData.append('session_id', this.attributionResult.session_id);
      if (this.commentaryPeriod.trim()) {
        formData.append('period', this.commentaryPeriod.trim());
      }

      const response = await this.apiService.generateAttributionCommentary(formData).toPromise();
      this.commentaryResponse = response;

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
    if (!this.attributionResult || !this.currentQuestion.trim()) return;

    this.isAnswering = true;
    
    try {
      const formData = new FormData();
      formData.append('session_id', this.attributionResult.session_id);
      formData.append('question', this.currentQuestion.trim());
      formData.append('mode', 'qa');

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

  // Collection management methods
  async loadAttributionCollections() {
    try {
      const response = await this.apiService.getAttributionCollections().toPromise();
      this.attributionCollections = response.collections || [];
    } catch (error) {
      console.error('Failed to load attribution collections:', error);
    }
  }

  refreshCollections() {
    this.loadAttributionCollections();
  }

  async deleteCollection(collection: CollectionInfo, event: Event) {
    event.stopPropagation();
    
    if (confirm(`Are you sure you want to delete the attribution collection "${collection.session_id}"? This action cannot be undone.`)) {
      try {
        await this.apiService.clearAttributionSession(collection.session_id).toPromise();
        this.showSuccess('Attribution collection deleted successfully');
        this.loadAttributionCollections();
      } catch (error: any) {
        this.showError(error.error?.detail || 'Failed to delete collection');
      }
    }
  }

  getStatusClass(status: string): string {
    switch (status) {
      case 'active':
        return 'status-active';
      case 'error':
        return 'status-error';
      default:
        return 'status-unknown';
    }
  }
}