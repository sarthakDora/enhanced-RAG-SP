import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { ChatMessage, ChatResponse, ChatSession, ChatRequest } from '../../models/chat.model';
import { DocumentSearchResult } from '../../models/document.model';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatChipsModule,
    MatProgressBarModule,
    MatTooltipModule,
    MatMenuModule
  ],
  template: `
    <div class="chat-container fade-in">
      <!-- Chat Header -->
      <div class="chat-header glass-card">
        <div class="session-info">
          <h2 class="gradient-text">{{ currentSession?.title || 'New Conversation' }}</h2>
          <p class="text-muted">Financial AI Assistant</p>
        </div>
        
        <div class="chat-controls">
          <button mat-icon-button 
                  class="glass-button"
                  (click)="startNewSession()"
                  title="New Conversation">
            <mat-icon>add</mat-icon>
          </button>
          
          <button mat-icon-button 
                  class="glass-button"
                  (click)="toggleSettings()"
                  title="Chat Settings">
            <mat-icon>tune</mat-icon>
          </button>
        </div>
      </div>

      <!-- Chat Messages -->
      <div class="chat-messages" #chatContainer>
        <div class="messages-list">
          <!-- Welcome Message -->
          <div *ngIf="messages.length === 0" class="welcome-message glass-card slide-up">
            <div class="welcome-content">
              <mat-icon class="welcome-icon">smart_toy</mat-icon>
              <h3 class="gradient-text">Welcome to Enhanced RAG</h3>
              <p>I'm your financial AI assistant. I can help you analyze financial documents, reports, and data. Ask me anything about your uploaded documents!</p>
              
              <div class="quick-actions">
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('What financial documents do I have uploaded?')">
                  <mat-icon>description</mat-icon>
                  View Documents
                </button>
                
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('Show me the latest revenue figures')">
                  <mat-icon>trending_up</mat-icon>
                  Revenue Analysis
                </button>
                
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('What are the key performance metrics?')">
                  <mat-icon>analytics</mat-icon>
                  Performance Metrics
                </button>
              </div>
            </div>
          </div>

          <!-- Chat Messages -->
          <div *ngFor="let message of messages; trackBy: trackMessage" 
               class="message-container"
               [class.user-message]="message.role === 'user'"
               [class.assistant-message]="message.role === 'assistant'">
            
            <!-- User Message -->
            <div *ngIf="message.role === 'user'" class="message user-msg glass-card slide-up">
              <div class="message-content">
                <p>{{ message.content }}</p>
              </div>
              <div class="message-time">
                {{ formatTime(message.timestamp) }}
              </div>
            </div>

            <!-- Assistant Message -->
            <div *ngIf="message.role === 'assistant'" class="message assistant-msg glass-card slide-up">
              <div class="message-header">
                <mat-icon class="assistant-icon">smart_toy</mat-icon>
                <span class="assistant-name">Financial AI</span>
                <div class="confidence-indicator" [class]="getConfidenceClass(message.confidence_score)">
                  <mat-icon>{{ getConfidenceIcon(message.confidence_score) }}</mat-icon>
                  <span>{{ getConfidenceText(message.confidence_score) }}</span>
                </div>
              </div>
              
              <div class="message-content" [innerHTML]="formatMessage(message.content)"></div>
              
              <!-- Sources -->
              <div *ngIf="message.sources && message.sources.length > 0" class="sources-section">
                <h4>Sources</h4>
                <div class="sources-list">
                  <div *ngFor="let source of message.sources" 
                       class="source-item glass-card"
                       (click)="openSourceDetails(source)">
                    <div class="source-header">
                      <mat-icon>{{ getDocumentTypeIcon(source.document_metadata.document_type) }}</mat-icon>
                      <span class="source-title">{{ source.document_metadata.filename }}</span>
                      <span class="source-score">{{ (source.score * 100).toFixed(1) }}%</span>
                    </div>
                    <p class="source-preview" *ngIf="!isSourceFileOnly(source.content)">{{ source.content.substring(0, 150) }}...</p>
                    <p class="source-description" *ngIf="isSourceFileOnly(source.content)">Referenced document for this response</p>
                    <div class="source-meta">
                      <span *ngIf="source.page_number">Page {{ source.page_number }}</span>
                      <span>{{ source.document_metadata.document_type }}</span>
                    </div>
                  </div>
                </div>
              </div>
              
              <div class="message-time">
                {{ formatTime(message.timestamp) }}
                <span *ngIf="message.processing_time_ms" class="processing-time">
                  • {{ message.processing_time_ms.toFixed(0) }}ms
                </span>
              </div>
            </div>
          </div>

          <!-- Typing Indicator -->
          <div *ngIf="isTyping" class="message assistant-msg glass-card typing-indicator">
            <div class="message-header">
              <mat-icon class="assistant-icon">smart_toy</mat-icon>
              <span class="assistant-name">Financial AI</span>
            </div>
            <div class="typing-animation">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Chat Input -->
      <div class="chat-input glass-card">
        <!-- File Attachment Area -->
        <div *ngIf="attachedFiles.length > 0" class="attached-files">
          <h4>Attached Files</h4>
          <div class="file-list">
            <div *ngFor="let file of attachedFiles; let i = index" 
                 class="attached-file-item glass-card">
              <mat-icon class="file-icon">{{ getFileIcon(file.name) }}</mat-icon>
              <div class="file-info">
                <span class="file-name">{{ file.name }}</span>
                <span class="file-size">{{ formatFileSize(file.size) }}</span>
              </div>
              <button mat-icon-button 
                      class="remove-file-btn"
                      (click)="removeFile(i)"
                      matTooltip="Remove file">
                <mat-icon>close</mat-icon>
              </button>
            </div>
          </div>
        </div>

        <div class="input-container">
          <!-- File Input (Hidden) -->
          <input #fileInput 
                 type="file" 
                 multiple 
                 accept=".pdf,.docx,.txt,.xlsx,.csv"
                 (change)="onFileSelected($event)"
                 style="display: none;">

          <!-- Attachment Button -->
          <button mat-icon-button 
                  class="glass-button attachment-btn"
                  (click)="fileInput.click()"
                  [disabled]="isLoading"
                  matTooltip="Attach files"
                  [matMenuTriggerFor]="attachmentMenu">
            <mat-icon>attach_file</mat-icon>
          </button>

          <!-- Attachment Menu -->
          <mat-menu #attachmentMenu="matMenu">
            <button mat-menu-item (click)="fileInput.click()">
              <mat-icon>upload_file</mat-icon>
              <span>Upload New Files</span>
            </button>
            <button mat-menu-item (click)="showExistingDocuments()">
              <mat-icon>folder</mat-icon>
              <span>Use Existing Documents</span>
            </button>
          </mat-menu>
          
          <mat-form-field appearance="outline" class="message-input">
            <input matInput 
                   [(ngModel)]="currentMessage" 
                   (keydown.enter)="sendMessage()"
                   [disabled]="isLoading"
                   placeholder="Ask about your financial documents..."
                   #messageInput>
          </mat-form-field>
          
          <button mat-fab 
                  color="primary"
                  class="send-button glass-button"
                  [disabled]="(!currentMessage.trim() && attachedFiles.length === 0) || isLoading"
                  (click)="sendMessage()">
            <mat-icon>{{ isLoading ? 'hourglass_empty' : 'send' }}</mat-icon>
          </button>
        </div>
        
        <!-- Progress Bar -->
        <mat-progress-bar *ngIf="isLoading" 
                          mode="indeterminate" 
                          class="progress-bar">
        </mat-progress-bar>

        <!-- Upload Progress -->
        <div *ngIf="isUploading" class="upload-progress">
          <div class="upload-status">
            <mat-icon class="upload-icon">cloud_upload</mat-icon>
            <span>Uploading files...</span>
            <span class="upload-count">{{ uploadedCount }}/{{ totalFiles }}</span>
          </div>
          <mat-progress-bar 
            mode="determinate" 
            [value]="uploadProgress"
            class="upload-progress-bar">
          </mat-progress-bar>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .chat-container {
      display: flex;
      flex-direction: column;
      height: calc(100vh - 120px);
      max-width: 1200px;
      margin: 0 auto;
      gap: 16px;
    }

    .chat-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 24px;
      margin-bottom: 0;
    }

    .session-info h2 {
      margin: 0;
      font-size: 24px;
    }

    .session-info p {
      margin: 4px 0 0 0;
      font-size: 14px;
    }

    .chat-controls {
      display: flex;
      gap: 8px;
    }

    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 0 8px;
    }

    .messages-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
      padding: 16px 0;
    }

    .welcome-message {
      text-align: center;
      padding: 40px 32px;
      margin: 40px auto;
      max-width: 600px;
    }

    .welcome-content .welcome-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      color: var(--text-primary);
      margin-bottom: 16px;
    }

    .welcome-content h3 {
      font-size: 28px;
      margin-bottom: 16px;
    }

    .welcome-content p {
      font-size: 16px;
      color: var(--text-secondary);
      margin-bottom: 32px;
      line-height: 1.6;
    }

    .quick-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      justify-content: center;
    }

    .quick-action {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 20px;
      font-size: 14px;
    }

    .message-container {
      display: flex;
      margin-bottom: 16px;
    }

    .message-container.user-message {
      justify-content: flex-end;
    }

    .message-container.assistant-message {
      justify-content: flex-start;
    }

    .message {
      max-width: 80%;
      padding: 16px 20px;
      border-radius: 16px;
      position: relative;
    }

    .user-msg {
      background: var(--accent-gradient) !important;
      color: white;
      margin-left: auto;
    }

    .assistant-msg {
      background: var(--glass-primary) !important;
      margin-right: auto;
    }

    .message-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      font-weight: 500;
    }

    .assistant-icon {
      color: var(--text-primary);
    }

    .confidence-indicator {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-left: auto;
      padding: 4px 8px;
      border-radius: 8px;
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

    .message-content {
      line-height: 1.6;
      word-wrap: break-word;
    }

    .message-content p {
      margin: 0 0 8px 0;
    }

    .message-content:last-child {
      margin-bottom: 0;
    }

    .sources-section {
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .sources-section h4 {
      margin: 0 0 12px 0;
      font-size: 14px;
      color: var(--text-secondary);
    }

    .sources-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .source-item {
      padding: 12px;
      cursor: pointer;
      transition: all 0.3s ease;
      border-radius: 8px;
    }

    .source-item:hover {
      transform: translateY(-1px);
      background: var(--glass-accent) !important;
    }

    .source-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .source-title {
      flex: 1;
      font-weight: 500;
      font-size: 14px;
    }

    .source-score {
      background: var(--glass-secondary);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
    }

    .source-preview {
      font-size: 13px;
      color: var(--text-secondary);
      margin: 8px 0;
      line-height: 1.4;
    }

    .source-description {
      font-size: 13px;
      color: var(--text-muted);
      margin: 8px 0;
      font-style: italic;
    }

    .source-meta {
      display: flex;
      gap: 12px;
      font-size: 12px;
      color: var(--text-muted);
    }

    .message-time {
      margin-top: 8px;
      font-size: 12px;
      color: var(--text-muted);
    }

    .processing-time {
      color: var(--text-muted);
    }

    .typing-indicator {
      margin-right: auto;
      max-width: 200px;
    }

    .typing-animation {
      display: flex;
      gap: 4px;
      padding: 8px 0;
    }

    .typing-dot {
      width: 8px;
      height: 8px;
      background: var(--text-secondary);
      border-radius: 50%;
      animation: typing 1.4s infinite ease-in-out;
    }

    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }

    @keyframes typing {
      0%, 80%, 100% {
        transform: scale(0.8);
        opacity: 0.5;
      }
      40% {
        transform: scale(1);
        opacity: 1;
      }
    }

    .chat-input {
      padding: 16px 20px;
      margin-top: auto;
    }

    .input-container {
      display: flex;
      gap: 12px;
      align-items: flex-end;
    }

    .message-input {
      flex: 1;
    }

    .message-input .mat-mdc-form-field-wrapper {
      background: transparent !important;
    }

    .send-button {
      min-width: 56px;
      min-height: 56px;
    }

    .progress-bar {
      margin-top: 8px;
      border-radius: 2px;
    }

    /* File Attachment Styles */
    .attached-files {
      margin-bottom: 16px;
      padding: 16px;
      background: var(--glass-secondary);
      border-radius: 12px;
    }

    .attached-files h4 {
      margin: 0 0 12px 0;
      font-size: 14px;
      color: var(--text-secondary);
    }

    .file-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .attached-file-item {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 8px 12px;
      border-radius: 8px;
      background: var(--glass-primary);
    }

    .file-icon {
      color: var(--text-primary);
    }

    .file-info {
      flex: 1;
      display: flex;
      flex-direction: column;
    }

    .file-name {
      font-size: 14px;
      font-weight: 500;
    }

    .file-size {
      font-size: 12px;
      color: var(--text-muted);
    }

    .remove-file-btn {
      opacity: 0.7;
    }

    .remove-file-btn:hover {
      opacity: 1;
      color: #f44336;
    }

    .attachment-btn {
      margin-right: 8px;
    }

    .upload-progress {
      margin-top: 12px;
    }

    .upload-status {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 14px;
    }

    .upload-icon {
      color: var(--text-primary);
    }

    .upload-count {
      margin-left: auto;
      background: var(--glass-secondary);
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
    }

    .upload-progress-bar {
      border-radius: 4px;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .chat-container {
        height: calc(100vh - 80px);
        gap: 8px;
      }

      .message {
        max-width: 90%;
        padding: 12px 16px;
      }

      .welcome-message {
        padding: 24px 20px;
        margin: 20px 8px;
      }

      .quick-actions {
        flex-direction: column;
      }

      .quick-action {
        width: 100%;
        justify-content: center;
      }
    }
  `]
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('chatContainer') chatContainer!: ElementRef;
  @ViewChild('messageInput') messageInput!: ElementRef;
  @ViewChild('fileInput') fileInput!: ElementRef;

  messages: ChatMessage[] = [];
  currentMessage = '';
  currentSession: ChatSession | null = null;
  isLoading = false;
  isTyping = false;
  showSettings = false;

  // File attachment properties
  attachedFiles: File[] = [];
  isUploading = false;
  uploadProgress = 0;
  uploadedCount = 0;
  totalFiles = 0;

  private subscriptions: Subscription[] = [];

  constructor(
    private apiService: ApiService,
    private snackBar: MatSnackBar,
    private dialog: MatDialog
  ) {}

  ngOnInit() {
    this.startNewSession();
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  ngAfterViewChecked() {
    this.scrollToBottom();
  }

  trackMessage(index: number, message: ChatMessage): string {
    return message.message_id;
  }

  async startNewSession() {
    try {
      const response = await this.apiService.createSession().toPromise();
      this.currentSession = {
        session_id: response.session_id,
        title: response.title,
        created_at: response.created_at,
        updated_at: response.created_at,
        messages: [],
        max_history: 50,
        context_window: 4000,
        temperature: 0.1,
        active_documents: [],
        financial_context: {},
        is_active: true,
        last_activity: response.created_at
      };
      this.messages = [];
    } catch (error) {
      this.showError('Failed to create new session');
    }
  }

  async sendMessage() {
    if (!this.currentMessage.trim() || this.isLoading) return;

    const message = this.currentMessage.trim();
    this.currentMessage = '';
    
    // Add user message
    const userMessage: ChatMessage = {
      message_id: this.generateId(),
      session_id: this.currentSession?.session_id || '',
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    
    this.messages.push(userMessage);
    this.isLoading = true;
    this.isTyping = true;

    try {
      // Upload files first if any are attached
      if (this.attachedFiles.length > 0) {
        await this.uploadAttachedFiles();
      }

      const chatRequest: ChatRequest = {
        session_id: this.currentSession?.session_id,
        message: message,
        use_rag: true,
        top_k: 10,
        rerank_top_k: 3,
        similarity_threshold: 0.3, // Lower threshold for better retrieval
        temperature: 0.1,
        max_tokens: 1000
      };

      const response: ChatResponse = await this.apiService.sendMessage(chatRequest).toPromise();
      
      // Add assistant message
      const assistantMessage: ChatMessage = {
        message_id: response.message_id,
        session_id: response.session_id,
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        sources: response.sources,
        confidence_score: response.confidence_score,
        processing_time_ms: response.total_time_ms
      };

      this.messages.push(assistantMessage);
      this.currentSession!.session_id = response.session_id;

    } catch (error) {
      this.showError('Failed to send message');
      console.error('Chat error:', error);
    } finally {
      this.isLoading = false;
      this.isTyping = false;
    }
  }

  sendQuickMessage(message: string) {
    this.currentMessage = message;
    this.sendMessage();
  }

  toggleSettings() {
    this.showSettings = !this.showSettings;
  }

  openSourceDetails(source: DocumentSearchResult) {
    // Open source details in a dialog
    console.log('Opening source details:', source);
  }

  formatTime(timestamp: string): string {
    return new Date(timestamp).toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  }

  formatMessage(content: string): string {
    // Basic markdown-like formatting
    return content
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  getConfidenceClass(score?: number): string {
    if (!score) return 'low';
    if (score >= 0.8) return 'high';
    if (score >= 0.6) return 'medium';
    return 'low';
  }

  getConfidenceIcon(score?: number): string {
    if (!score || score === 0) return 'help_outline';
    if (score >= 0.8) return 'check_circle';
    if (score >= 0.6) return 'info';
    return 'warning';
  }

  getConfidenceText(score?: number): string {
    if (!score) return 'Unknown';
    if (score >= 0.8) return 'High';
    if (score >= 0.6) return 'Medium';
    return 'Low';
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

  isSourceFileOnly(content: string): boolean {
    // Check if the content is just indicating the source file (not actual chunk content)
    return content.startsWith('Source:') || content.length < 50;
  }

  private scrollToBottom() {
    try {
      if (this.chatContainer) {
        const element = this.chatContainer.nativeElement;
        element.scrollTop = element.scrollHeight;
      }
    } catch (err) {}
  }

  private showError(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 5000,
      horizontalPosition: 'center',
      verticalPosition: 'top'
    });
  }

  private generateId(): string {
    return Math.random().toString(36).substring(2) + Date.now().toString(36);
  }

  // File attachment methods
  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files) {
      const files = Array.from(input.files);
      this.attachedFiles.push(...files);
    }
    // Clear input to allow selecting same file again
    input.value = '';
  }

  removeFile(index: number) {
    this.attachedFiles.splice(index, 1);
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
        return 'table_chart';
      case 'csv':
        return 'grid_on';
      default:
        return 'insert_drive_file';
    }
  }

  formatFileSize(bytes: number): string {
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  }

  async uploadAttachedFiles(): Promise<void> {
    if (this.attachedFiles.length === 0) return;

    this.isUploading = true;
    this.uploadProgress = 0;
    this.uploadedCount = 0;
    this.totalFiles = this.attachedFiles.length;

    try {
      const uploadPromises = this.attachedFiles.map(async (file, index) => {
        try {
          const response = await this.apiService.uploadDocuments(
            [file],
            'other', // Default document type
            'chat-attachment'
          ).toPromise();
          
          this.uploadedCount++;
          this.uploadProgress = (this.uploadedCount / this.totalFiles) * 100;
          
          return response;
        } catch (error) {
          console.error(`Failed to upload ${file.name}:`, error);
          throw error;
        }
      });

      await Promise.all(uploadPromises);
      
      this.showSuccess(`Successfully uploaded ${this.uploadedCount} file(s)`);
      
      // Clear attached files after successful upload
      this.attachedFiles = [];
      
    } catch (error) {
      this.showError('Some files failed to upload. Please try again.');
    } finally {
      this.isUploading = false;
      this.uploadProgress = 0;
      this.uploadedCount = 0;
      this.totalFiles = 0;
    }
  }

  showExistingDocuments() {
    // Navigate to documents page or show existing documents dialog
    console.log('Show existing documents');
    // You could implement a dialog here to show existing documents
    // and allow users to select which ones to use in the chat
  }

  private showSuccess(message: string) {
    this.snackBar.open(message, 'Close', {
      duration: 3000,
      panelClass: ['success-snackbar']
    });
  }
}