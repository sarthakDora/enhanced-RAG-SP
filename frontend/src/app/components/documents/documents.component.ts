import { Component, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { DocumentType, DocumentListItem, DocumentStats } from '../../models/document.model';

interface UploadFile {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
}

@Component({
  selector: 'app-documents',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatChipsModule,
    MatProgressBarModule,
    MatSelectModule,
    MatInputModule
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
                 accept=".pdf,.docx,.txt"
                 (change)="onFileSelected($event)"
                 style="display: none;">
          
          <div class="upload-content">
            <mat-icon class="upload-icon">cloud_upload</mat-icon>
            <h3>Drag & Drop Files Here</h3>
            <p>Or click to browse files</p>
            <p class="file-info">Supported formats: PDF, DOCX, TXT (Max 100MB)</p>
          </div>
        </div>

        <!-- Upload Configuration -->
        <div class="upload-config glass-card" *ngIf="selectedFiles.length > 0">
          <h4>Upload Configuration</h4>
          
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
              Upload {{ selectedFiles.length }} File(s)
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
                  {{ getStatusIcon(uploadFile.status) }}
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
              <h3>{{ stats.average_chunks_per_document?.toFixed(1) }}</h3>
              <p>Avg Chunks/Doc</p>
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

      .stats-grid {
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      }

      .documents-grid {
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
    
    // Subscribe to documents updates
    const docUpdateSub = this.apiService.documentsUpdated$.subscribe(() => {
      this.refreshDocuments();
    });
    this.subscriptions.push(docUpdateSub);
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
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
    
    if (validFiles.length !== files.length) {
      this.showError('Some files were rejected. Only PDF, DOCX, and TXT files under 100MB are allowed.');
    }
  }

  private isValidFile(file: File): boolean {
    const allowedTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    const maxSize = 100 * 1024 * 1024; // 100MB
    
    return allowedTypes.includes(file.type) && file.size <= maxSize;
  }

  clearSelection() {
    this.selectedFiles = [];
    this.uploadFilesList = [];
    this.tags = '';
  }

  async uploadFiles() {
    if (this.selectedFiles.length === 0) return;

    this.isUploading = true;
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
      default:
        return 'insert_drive_file';
    }
  }

  getStatusIcon(status: string): string {
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
}