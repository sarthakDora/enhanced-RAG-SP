import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, AfterViewInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';

import { ApiService } from '../../services/api.service';
import { ChatMessage, ChatResponse, ChatSession, ChatRequest } from '../../models/chat.model';
import { DocumentSearchResult, DocumentType } from '../../models/document.model';
import { PromptDialogComponent } from './prompt-dialog.component';
import { ChatSettingsDialogComponent } from './chat-settings-dialog.component';

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
    MatMenuModule,
    MatSelectModule,
    MatFormFieldModule,
    MatDialogModule,
    MatSlideToggleModule
  ],
  template: `
    <div class="chat-container fade-in">
      <!-- Chat Header -->
      <div class="chat-header glass-card" [class.collapsed]="isHeaderCollapsed">
        <div class="session-info">
          <h2 class="gradient-text">{{ currentSession?.title || 'New Conversation' }}</h2>
          <p class="text-muted">
            Financial AI Assistant
            <span *ngIf="selectedDocumentType === 'performance_attribution'" 
                  class="mode-indicator"
                  [class.commentary-active]="commentaryMode"
                  [class.qa-active]="!commentaryMode">
              • {{ commentaryMode ? 'Commentary Mode' : 'Q&A Mode' }}
            </span>
          </p>
          
          <!-- Document Type Selection -->
          <div class="document-type-selection" *ngIf="currentSession && !isHeaderCollapsed">
            <mat-form-field appearance="outline" class="document-type-field">
              <mat-label>Document Focus</mat-label>
              <mat-select [(ngModel)]="selectedDocumentType" 
                          (selectionChange)="onDocumentTypeChange($event.value)">
                <mat-option value="">All Documents</mat-option>
                <mat-option value="performance_attribution">Performance Attribution</mat-option>
                <mat-option value="vbam_support">VBAM Support Documentation</mat-option>
                <mat-option value="financial_report">Financial Reports</mat-option>
                <mat-option value="market_analysis">Market Analysis</mat-option>
                <mat-option value="compliance_report">Compliance Reports</mat-option>
                <mat-option value="legal_contract">Legal Contracts</mat-option>
                <mat-option value="other">Other</mat-option>
              </mat-select>
            </mat-form-field>
            
            <!-- Clear Documents Button -->
            <button mat-icon-button 
                    class="glass-button clear-docs-btn"
                    *ngIf="selectedDocumentType"
                    (click)="clearDocuments()"
                    [title]="'Clear ' + getDocumentTypeName(selectedDocumentType) + ' documents'">
              <mat-icon>clear_all</mat-icon>
            </button>
          </div>
          
          <!-- Commentary Mode Toggle -->
          <div class="commentary-mode-section" *ngIf="currentSession && selectedDocumentType === 'performance_attribution' && !isHeaderCollapsed">
            <mat-slide-toggle 
              [(ngModel)]="commentaryMode" 
              class="commentary-toggle"
              (change)="onCommentaryModeChange($event.checked)">
              <span class="toggle-label">Generate Commentary</span>
            </mat-slide-toggle>
            <p class="toggle-description">
              <strong>{{ commentaryMode ? 'Commentary Mode:' : 'Q&A Mode:' }}</strong>
              {{ commentaryMode ? 'Generate structured attribution analysis with Executive Summary, Performance Overview, and detailed attribution breakdowns.' : 'Ask specific questions about the uploaded documents. Example: "What was the best performing sector?" or "Show me attribution effects for Technology."' }}
            </p>
          </div>
        </div>
        
        <div class="chat-controls">
          <button mat-icon-button 
                  class="glass-button"
                  (click)="toggleHeaderCollapse()"
                  [title]="isHeaderCollapsed ? 'Expand header' : 'Collapse header'">
            <mat-icon>{{ isHeaderCollapsed ? 'expand_more' : 'expand_less' }}</mat-icon>
          </button>
          
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
        <!-- Scroll to bottom button -->
        <button *ngIf="!shouldAutoScroll" 
                class="scroll-to-bottom-btn glass-button"
                (click)="scrollToBottomManual()"
                mat-fab
                color="primary">
          <mat-icon>keyboard_arrow_down</mat-icon>
        </button>
        
        <div class="messages-list">
          <!-- Welcome Message -->
          <div *ngIf="messages.length === 0" class="welcome-message glass-card slide-up">
            <div class="welcome-content">
              <mat-icon class="welcome-icon">smart_toy</mat-icon>
              <h3 class="gradient-text">
                <span *ngIf="selectedDocumentType === 'vbam_support'">VBAM Support Assistant</span>
                <span *ngIf="selectedDocumentType !== 'vbam_support'">Welcome to VBAM RAG</span>
              </h3>
              <p *ngIf="selectedDocumentType === 'vbam_support'">
                I'm your VBAM support specialist. I can help you understand VBAM features, navigation, inputs, and outputs across all components (IPR, Analytics Report, Factsheet, Holdings and Risk). 
                I'll maintain context from our conversation to provide better assistance.
              </p>
              <p *ngIf="selectedDocumentType !== 'vbam_support'">
                I'm your financial AI assistant. I can help you analyze financial documents, reports, and data. Ask me anything about your uploaded documents!
              </p>
              
              <div class="quick-actions">
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('What financial documents do I have uploaded?')"
                        *ngIf="selectedDocumentType !== 'vbam_support'">
                  <mat-icon>description</mat-icon>
                  View Documents
                </button>
                
                <!-- VBAM-specific quick actions -->
                <ng-container *ngIf="selectedDocumentType === 'vbam_support'">
                  <button class="glass-button quick-action"
                          (click)="sendQuickMessage('What are the inputs for IPR?')">
                    <mat-icon>input</mat-icon>
                    IPR Inputs
                  </button>
                  
                  <button class="glass-button quick-action"
                          (click)="sendQuickMessage('How do I navigate to Analytics Report?')">
                    <mat-icon>analytics</mat-icon>
                    Analytics Navigation
                  </button>
                  
                  <button class="glass-button quick-action"
                          (click)="sendQuickMessage('What components are available in VBAM?')">
                    <mat-icon>dashboard</mat-icon>
                    VBAM Components
                  </button>
                  
                  <button class="glass-button quick-action"
                          (click)="sendQuickMessage('Summarize our conversation so far')"
                          *ngIf="messages.length > 2">
                    <mat-icon>summarize</mat-icon>
                    Summarize Conversation
                  </button>
                </ng-container>
                
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('Show me the latest revenue figures')"
                        *ngIf="selectedDocumentType !== 'vbam_support'">
                  <mat-icon>trending_up</mat-icon>
                  Revenue Analysis
                </button>
                
                <button class="glass-button quick-action"
                        (click)="sendQuickMessage('What are the key performance metrics?')"
                        *ngIf="selectedDocumentType !== 'vbam_support'">
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
                <div class="header-actions">
                  <button mat-icon-button 
                          class="prompt-button glass-button"
                          (click)="showPrompt(message)"
                          matTooltip="View prompt sent to LLM">
                    <mat-icon>code</mat-icon>
                  </button>
                  <div class="confidence-indicator" [class]="getConfidenceClass(message.confidence_score)">
                    <mat-icon>{{ getConfidenceIcon(message.confidence_score) }}</mat-icon>
                    <span>{{ getConfidenceText(message.confidence_score) }}</span>
                  </div>
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
          <div class="attached-files-header">
            <h4>Attached Files</h4>
            <mat-form-field appearance="outline" class="upload-type-field">
              <mat-label>Upload as</mat-label>
              <mat-select [(ngModel)]="uploadDocumentType">
                <mat-option value="performance_attribution">Performance Attribution</mat-option>
                <mat-option value="vbam_support">VBAM Support Documentation</mat-option>
                <mat-option value="financial_report">Financial Reports</mat-option>
                <mat-option value="market_analysis">Market Analysis</mat-option>
                <mat-option value="compliance_report">Compliance Reports</mat-option>
                <mat-option value="legal_contract">Legal Contracts</mat-option>
                <mat-option value="other">Other</mat-option>
              </mat-select>
            </mat-form-field>
          </div>
          
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
                   (focus)="onInputFocus()"
                   (input)="onInputChange()"
                   [disabled]="isLoading"
                   [placeholder]="getInputPlaceholder()"
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
      height: calc(100vh - 80px);
      max-width: 1200px;
      margin: 0 auto;
      gap: 12px;
      padding: 8px;
    }

    .chat-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      padding: 16px 20px;
      margin-bottom: 0;
      gap: 16px;
      flex-shrink: 0;
      transition: all 0.3s ease;
      overflow: hidden;
    }

    .chat-header.collapsed {
      padding: 8px 20px;
      max-height: 60px;
    }

    .chat-header.collapsed .session-info {
      overflow: hidden;
    }

    .chat-header.collapsed .session-info h2,
    .chat-header.collapsed .session-info p {
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .session-info h2 {
      margin: 0;
      font-size: 24px;
      color: var(--text-primary) !important;
      font-weight: 700;
    }

    .session-info p {
      margin: 4px 0 0 0;
      font-size: 14px;
      color: var(--text-secondary) !important;
      font-weight: 500;
    }

    .mode-indicator {
      font-weight: 600;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-left: 8px;
    }

    .mode-indicator.commentary-active {
      background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
      color: white;
      box-shadow: 0 2px 4px rgba(79, 172, 254, 0.3);
    }

    .mode-indicator.qa-active {
      background: rgba(108, 117, 125, 0.1);
      color: #6c757d;
      border: 1px solid rgba(108, 117, 125, 0.3);
    }

    .document-type-selection {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
    }

    .document-type-field {
      min-width: 200px;
    }

    .document-type-field .mat-mdc-form-field-wrapper {
      background: transparent !important;
    }

    .clear-docs-btn {
      color: #f44336 !important;
    }

    .clear-docs-btn:hover {
      background: rgba(244, 67, 54, 0.1) !important;
    }

    .chat-controls {
      display: flex;
      gap: 8px;
    }

    .chat-messages {
      flex: 1;
      overflow-y: auto;
      padding: 0 12px;
      position: relative;
      min-height: 0;
      background: rgba(0, 0, 0, 0.02);
      border-radius: 12px;
      border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .scroll-to-bottom-btn {
      position: absolute !important;
      bottom: 20px;
      right: 20px;
      z-index: 1000;
      width: 48px !important;
      height: 48px !important;
      min-width: 48px !important;
      animation: fadeIn 0.3s ease-in-out;
    }

    @keyframes fadeIn {
      from { opacity: 0; transform: scale(0.8); }
      to { opacity: 1; transform: scale(1); }
    }

    .messages-list {
      display: flex;
      flex-direction: column;
      gap: 20px;
      padding: 20px 0;
      min-height: 100%;
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
      padding: 20px 24px;
      border-radius: 16px;
      position: relative;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .user-msg {
      background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
      color: #ffffff !important;
      margin-left: auto;
      font-weight: 500;
    }

    .assistant-msg {
      background: #ffffff !important;
      margin-right: auto;
      border: 1px solid #e2e8f0 !important;
      color: #1a202c !important;
    }

    .message-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
      font-weight: 600;
    }

    .assistant-icon {
      color: #4a5568 !important;
      font-size: 20px;
    }

    .assistant-name {
      color: #1a202c !important;
      font-size: 15px;
      font-weight: 700;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 4px;
      margin-left: auto;
    }

    .prompt-button {
      color: var(--text-secondary) !important;
      opacity: 0.7;
      transition: all 0.3s ease;
      width: 32px !important;
      height: 32px !important;
      min-width: 32px !important;
    }

    .prompt-button:hover {
      opacity: 1;
      color: var(--accent-color) !important;
      background: rgba(255, 255, 255, 0.1) !important;
    }

    .prompt-button mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }

    .confidence-indicator {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid transparent;
    }

    .confidence-indicator.high {
      background: #dcfce7;
      color: #166534 !important;
      border-color: #bbf7d0;
    }

    .confidence-indicator.medium {
      background: #fef3c7;
      color: #92400e !important;
      border-color: #fde68a;
    }

    .confidence-indicator.low {
      background: #fecaca;
      color: #991b1b !important;
      border-color: #fca5a5;
    }

    .message-content {
      line-height: 1.7;
      word-wrap: break-word;
      color: #1a202c !important;
      font-size: 15px;
      font-weight: 500;
      text-shadow: none;
    }

    .user-msg .message-content {
      color: #ffffff !important;
      font-weight: 600;
      text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    }

    .assistant-msg .message-content {
      color: #1a202c !important;
      font-weight: 500;
    }

    .message-content p {
      margin: 0 0 12px 0;
      color: inherit !important;
    }

    .message-content p:last-child {
      margin-bottom: 0;
    }

    .message-content strong {
      color: inherit !important;
      font-weight: 700;
    }

    .message-content em {
      color: inherit !important;
      font-style: italic;
    }

    /* Ensure all text elements inherit proper color */
    .message-content * {
      color: inherit !important;
    }

    .sources-section {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 2px solid #f7fafc;
    }

    .sources-section h4 {
      margin: 0 0 16px 0;
      font-size: 15px;
      color: #4a5568 !important;
      font-weight: 700;
    }

    .sources-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .source-item {
      padding: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      border-radius: 10px;
      background: #f8fafc !important;
      border: 1px solid #e2e8f0;
      margin-bottom: 8px;
    }

    .source-item:hover {
      transform: translateY(-2px);
      background: #f0f4f7 !important;
      border-color: #cbd5e0;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }

    .source-header {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }

    .source-title {
      flex: 1;
      font-weight: 700;
      font-size: 14px;
      color: #1a202c !important;
    }

    .source-score {
      background: #e0f2fe;
      color: #0277bd !important;
      padding: 4px 10px;
      border-radius: 12px;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid #b3e5fc;
    }

    .source-preview {
      font-size: 13px;
      color: #4a5568 !important;
      margin: 10px 0;
      line-height: 1.5;
      font-weight: 400;
    }

    .source-description {
      font-size: 13px;
      color: #6b7280 !important;
      margin: 10px 0;
      font-style: italic;
      font-weight: 500;
    }

    .source-meta {
      display: flex;
      gap: 12px;
      font-size: 12px;
      color: #6b7280 !important;
      font-weight: 500;
      margin-top: 8px;
    }

    .source-meta span {
      background: #f3f4f6;
      padding: 2px 8px;
      border-radius: 8px;
      color: #374151 !important;
      font-weight: 500;
    }

    .message-time {
      margin-top: 12px;
      font-size: 12px;
      color: #6b7280 !important;
      font-weight: 600;
    }

    .user-msg .message-time {
      color: rgba(255, 255, 255, 0.9) !important;
    }

    .assistant-msg .message-time {
      color: #6b7280 !important;
    }

    .processing-time {
      color: inherit !important;
      font-weight: 500;
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
      flex-shrink: 0;
      background: var(--glass-primary);
      border-top: 1px solid rgba(255, 255, 255, 0.1);
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

    .attached-files-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .attached-files h4 {
      margin: 0;
      font-size: 14px;
      color: var(--text-secondary);
    }

    .upload-type-field {
      min-width: 180px;
    }

    .upload-type-field .mat-mdc-form-field-wrapper {
      background: transparent !important;
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

    /* Commentary Mode Toggle Styles */
    .commentary-mode-section {
      margin-top: 16px;
      padding: 16px;
      background: linear-gradient(135deg, rgba(79, 172, 254, 0.08) 0%, rgba(0, 242, 254, 0.08) 100%);
      border-radius: 12px;
      border: 1px solid rgba(79, 172, 254, 0.2);
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }

    .commentary-toggle {
      margin-bottom: 12px;
    }

    .commentary-toggle .mat-slide-toggle-bar {
      background-color: rgba(255, 255, 255, 0.2);
    }

    .commentary-toggle.mat-checked .mat-slide-toggle-bar {
      background-color: #4facfe;
    }

    .toggle-label {
      font-weight: 600;
      margin-left: 8px;
      color: var(--text-primary);
      font-size: 14px;
    }

    .toggle-description {
      margin: 0;
      font-size: 13px;
      color: var(--text-secondary);
      line-height: 1.5;
      background: rgba(255, 255, 255, 0.8);
      padding: 8px 12px;
      border-radius: 8px;
      border-left: 3px solid #4facfe;
    }

    .toggle-description strong {
      color: #4facfe;
    }

    /* Responsive Design */
    @media (max-width: 768px) {
      .chat-container {
        height: calc(100vh - 60px);
        gap: 8px;
        padding: 4px;
      }

      .chat-header {
        padding: 12px 16px;
      }

      .message {
        max-width: 92%;
        padding: 12px 16px;
      }

      .welcome-message {
        padding: 20px 16px;
        margin: 16px 4px;
      }

      .quick-actions {
        flex-direction: column;
        gap: 8px;
      }

      .quick-action {
        width: 100%;
        justify-content: center;
        padding: 10px 16px;
      }

      .commentary-mode-section {
        margin-top: 12px;
        padding: 12px;
      }

      .toggle-description {
        font-size: 12px;
        padding: 6px 10px;
      }

      .chat-messages {
        padding: 0 8px;
      }

      .messages-list {
        gap: 16px;
        padding: 16px 0;
      }
    }

    /* Scrollbar Styling */
    .chat-messages::-webkit-scrollbar {
      width: 6px;
    }

    .chat-messages::-webkit-scrollbar-track {
      background: rgba(0, 0, 0, 0.05);
      border-radius: 3px;
    }

    .chat-messages::-webkit-scrollbar-thumb {
      background: rgba(79, 172, 254, 0.3);
      border-radius: 3px;
    }

    .chat-messages::-webkit-scrollbar-thumb:hover {
      background: rgba(79, 172, 254, 0.5);
    }
  `]
})
export class ChatComponent implements OnInit, OnDestroy, AfterViewInit, AfterViewChecked {
  @ViewChild('chatContainer') chatContainer!: ElementRef;
  @ViewChild('messageInput') messageInput!: ElementRef;
  @ViewChild('fileInput') fileInput!: ElementRef;

  messages: ChatMessage[] = [];
  currentMessage = '';
  currentSession: ChatSession | null = null;
  isLoading = false;
  isTyping = false;
  
  // Scroll management
  private isUserScrolling = false;
  shouldAutoScroll = true; // Made public for template access
  private scrollThreshold = 100;
  
  // Header collapse management
  isHeaderCollapsed = false;

  // Document type selection
  selectedDocumentType: string = '';
  uploadDocumentType: string = 'other';
  
  // Commentary mode toggle
  commentaryMode: boolean = false;

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
    private dialog: MatDialog,
    private router: Router
  ) {}

  ngOnInit() {
    this.startNewSession();
  }

  ngAfterViewInit() {
    if (this.chatContainer) {
      const element = this.chatContainer.nativeElement;
      
      // Add scroll event listener to detect user scrolling
      element.addEventListener('scroll', this.onScroll.bind(this), { passive: true });
      
      // Add wheel event listener to detect when user starts scrolling
      element.addEventListener('wheel', this.onUserScroll.bind(this), { passive: true });
      
      // Add touch events for mobile scrolling detection
      element.addEventListener('touchstart', this.onUserScroll.bind(this), { passive: true });
    }
  }

  ngOnDestroy() {
    this.subscriptions.forEach(sub => sub.unsubscribe());
  }

  ngAfterViewChecked() {
    if (this.shouldAutoScroll && !this.isUserScrolling) {
      this.scrollToBottom();
    }
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
        document_type: undefined,
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
      this.selectedDocumentType = '';
      this.expandHeaderOnNewSession();
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
    
    // Enable auto-scroll for new messages
    this.shouldAutoScroll = true;
    this.isUserScrolling = false;
    
    // Auto-collapse header when typing
    this.autoCollapseHeader();

    try {
      // Upload files first if any are attached
      if (this.attachedFiles.length > 0) {
        await this.uploadAttachedFiles();
      }

      // Get current settings for this session to apply to chat request
      let currentSettings;
      try {
        currentSettings = await this.apiService.getSettings(this.currentSession?.session_id).toPromise();
      } catch (error) {
        console.log('Using default settings for chat request');
        currentSettings = {
          temperature: 0.1,
          max_tokens: 1000,
          use_rag: true,
          top_k: 10,
          rerank_top_k: 3,
          similarity_threshold: 0.7,
          reranking_strategy: 'hybrid'
        };
      }

      const chatRequest: ChatRequest = {
        session_id: this.currentSession?.session_id,
        message: message,
        document_type: this.selectedDocumentType as DocumentType || undefined,
        use_rag: currentSettings.use_rag,
        top_k: currentSettings.top_k,
        rerank_top_k: currentSettings.rerank_top_k,
        similarity_threshold: currentSettings.similarity_threshold,
        reranking_strategy: currentSettings.reranking_strategy,
        temperature: currentSettings.temperature,
        max_tokens: currentSettings.max_tokens,
        commentary_mode: this.commentaryMode, // Add commentary mode flag
        // Include conversation history for VBAM support documentation
        conversation_history: this.selectedDocumentType === 'vbam_support' ? this.getLastConversations(5) : undefined
      };

      console.log('Sending chat request:', {
        document_type: chatRequest.document_type,
        commentary_mode: chatRequest.commentary_mode,
        conversation_history_length: chatRequest.conversation_history?.length || 0,
        message: chatRequest.message.substring(0, 50) + '...'
      });

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
        processing_time_ms: response.total_time_ms,
        prompt: response.prompt
      };

      this.messages.push(assistantMessage);
      this.currentSession!.session_id = response.session_id;

    } catch (error) {
      this.showError('Failed to send message');
      console.error('Chat error:', error);
    } finally {
      this.isLoading = false;
      this.isTyping = false;
      
      // Auto-collapse header when receiving response
      this.autoCollapseHeader();
    }
  }

  sendQuickMessage(message: string) {
    this.currentMessage = message;
    this.sendMessage();
  }

  toggleSettings() {
    const dialogRef = this.dialog.open(ChatSettingsDialogComponent, {
      width: '700px',
      maxWidth: '95vw',
      maxHeight: '90vh',
      data: { 
        sessionId: this.currentSession?.session_id,
        documentType: this.selectedDocumentType 
      },
      panelClass: 'chat-settings-dialog-panel'
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result?.saved) {
        console.log('Chat settings updated:', result.settings);
        this.showSuccess('Chat settings have been updated for this session');
        // Settings are automatically applied to subsequent chat requests
        // through the getSettings() call in sendMessage()
      }
    });
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
    // Enhanced markdown-like formatting for VBAM responses including conversation summaries
    return content
      // Handle headers
      .replace(/^### (.*$)/gm, '<h4 style="margin: 16px 0 8px 0; color: #2563eb; font-weight: 600;">$1</h4>')
      .replace(/^## (.*$)/gm, '<h3 style="margin: 20px 0 12px 0; color: #1e40af; font-weight: 700; border-bottom: 2px solid #e5e7eb; padding-bottom: 4px;">$1</h3>')
      .replace(/^# (.*$)/gm, '<h2 style="margin: 24px 0 16px 0; color: #1e3a8a; font-weight: 800;">$1</h2>')
      // Handle bullet points
      .replace(/^\* (.*$)/gm, '<div style="margin: 4px 0; padding-left: 16px; position: relative;"><span style="position: absolute; left: 0; top: 0; color: #6b7280;">•</span>$1</div>')
      // Handle bold and italic
      .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #374151; font-weight: 600;">$1</strong>')
      .replace(/\*(.*?)\*/g, '<em style="color: #4b5563; font-style: italic;">$1</em>')
      // Handle line breaks
      .replace(/\n\n/g, '<div style="margin: 12px 0;"></div>')
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
      'vbam_support': 'precision_manufacturing',
      'other': 'description'
    };
    return iconMap[type] || 'description';
  }

  isSourceFileOnly(content: string): boolean {
    // Check if the content is just indicating the source file (not actual chunk content)
    return content.startsWith('Source:') || content.length < 50;
  }

  onScroll(event: Event) {
    if (!this.chatContainer) return;
    
    const element = this.chatContainer.nativeElement;
    const scrollTop = element.scrollTop;
    const scrollHeight = element.scrollHeight;
    const clientHeight = element.clientHeight;
    
    // Check if user is near the bottom (within threshold)
    const isNearBottom = (scrollHeight - scrollTop - clientHeight) < this.scrollThreshold;
    
    if (isNearBottom) {
      this.shouldAutoScroll = true;
      this.isUserScrolling = false;
    } else {
      this.shouldAutoScroll = false;
    }
  }

  onUserScroll(event: Event) {
    // User initiated scroll action
    this.isUserScrolling = true;
    this.shouldAutoScroll = false;
    
    // Reset the user scrolling flag after a delay
    setTimeout(() => {
      this.isUserScrolling = false;
    }, 1000);
  }

  scrollToBottomManual() {
    // Manually scroll to bottom and enable auto-scroll
    this.shouldAutoScroll = true;
    this.isUserScrolling = false;
    
    try {
      if (this.chatContainer) {
        const element = this.chatContainer.nativeElement;
        element.scrollTo({
          top: element.scrollHeight,
          behavior: 'smooth'
        });
      }
    } catch (err) {}
  }

  private scrollToBottom() {
    try {
      if (this.chatContainer && this.shouldAutoScroll) {
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

  /**
   * Get the last N conversations (user-assistant pairs) for VBAM context memory
   * This provides context awareness for follow-up questions
   */
  private getLastConversations(count: number): ChatMessage[] {
    if (!this.messages || this.messages.length === 0) {
      return [];
    }

    // Exclude the current user message that was just added
    const previousMessages = this.messages.slice(0, -1);
    
    if (previousMessages.length === 0) {
      return [];
    }

    // Get the last N*2 messages to ensure we get N complete conversations
    const maxMessages = Math.min(count * 2, previousMessages.length);
    const recentMessages = previousMessages.slice(-maxMessages);
    
    // Build conversation history ensuring we have complete user-assistant pairs
    const conversationHistory: ChatMessage[] = [];
    
    for (let i = 0; i < recentMessages.length; i++) {
      const msg = recentMessages[i];
      conversationHistory.push(msg);
    }
    
    // Log for debugging
    console.log('VBAM Context: Sending conversation history:', {
      total_messages: this.messages.length,
      previous_messages: previousMessages.length,
      history_messages: conversationHistory.length,
      history_preview: conversationHistory.map(m => ({ role: m.role, content: m.content.substring(0, 50) + '...' }))
    });
    
    return conversationHistory;
  }

  /**
   * Check if the user is asking for a conversation summary
   */
  private isSummaryRequest(message: string): boolean {
    const summaryKeywords = [
      'summarize', 'summary', 'recap', 'review', 'what did we discuss',
      'conversation summary', 'what have we talked about', 'overview of our chat'
    ];
    const lowerMessage = message.toLowerCase();
    return summaryKeywords.some(keyword => lowerMessage.includes(keyword));
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
      // Check if Performance Attribution is selected
      if (this.uploadDocumentType === 'performance_attribution') {
        await this.uploadAttributionFiles();
      } else {
        await this.uploadRegularDocuments();
      }
      
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

  private async uploadAttributionFiles(): Promise<void> {
    // Filter for Excel files only for attribution
    const excelFiles = this.attachedFiles.filter(file => 
      file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' || 
      file.type === 'application/vnd.ms-excel'
    );

    if (excelFiles.length === 0) {
      throw new Error('No Excel files found for attribution processing. Please upload .xlsx or .xls files.');
    }

    // Process each Excel file through attribution API
    const uploadPromises = excelFiles.map(async (file, index) => {
      try {
        const formData = new FormData();
        formData.append('file', file);
        // Optional: Add session_id if needed
        // formData.append('session_id', `chat_${Date.now()}`);

        const response = await this.apiService.uploadAttributionFile(formData).toPromise();
        
        this.uploadedCount++;
        this.uploadProgress = (this.uploadedCount / this.totalFiles) * 100;
        
        // Show attribution processing success message
        this.showSuccess(`Attribution file "${file.name}" processed successfully! Asset class: ${response.asset_class}, Chunks: ${response.chunks_created}`);
        
        return response;
      } catch (error) {
        console.error(`Failed to process attribution file ${file.name}:`, error);
        throw error;
      }
    });

    await Promise.all(uploadPromises);
  }

  private async uploadRegularDocuments(): Promise<void> {
    const uploadPromises = this.attachedFiles.map(async (file, index) => {
      try {
        const response = await this.apiService.uploadDocuments(
          [file],
          this.uploadDocumentType,
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

  // Document type selection methods
  onDocumentTypeChange(documentType: string) {
    this.selectedDocumentType = documentType;
    if (this.currentSession) {
      this.currentSession.document_type = documentType as DocumentType;
    }
    
    // Redirect to attribution page if performance attribution is selected
    if (documentType === 'performance_attribution') {
      this.showAttributionRedirectDialog();
    }
  }

  showAttributionRedirectDialog() {
    const confirmRedirect = confirm(
      'Performance Attribution analysis is best done on the dedicated Attribution page.\n\n' +
      'Would you like to go to the Attribution page for:\n' +
      '• Professional attribution commentary generation\n' +
      '• Excel file upload and processing\n' +
      '• Institutional-grade analysis tools\n\n' +
      'Click OK to go to Attribution page, or Cancel to stay here.'
    );
    
    if (confirmRedirect) {
      this.router.navigate(['/attribution']);
    } else {
      // User chose to stay, show info message
      this.showSuccess('💡 Tip: For best attribution analysis experience, visit the Attribution page from the main menu');
    }
  }

  async clearDocuments() {
    if (!this.selectedDocumentType) return;

    try {
      const response = await this.apiService.clearDocumentsByCategory(this.selectedDocumentType).toPromise();
      this.showSuccess(`Cleared ${response.documents_cleared} ${this.getDocumentTypeName(this.selectedDocumentType)} documents`);
    } catch (error) {
      this.showError('Failed to clear documents');
    }
  }

  getDocumentTypeName(type: string): string {
    const typeNames: { [key: string]: string } = {
      'performance_attribution': 'Performance Attribution',
      'vbam_support': 'VBAM Support Documentation',
      'financial_report': 'Financial Report',
      'market_analysis': 'Market Analysis', 
      'compliance_report': 'Compliance Report',
      'legal_contract': 'Legal Contract',
      'other': 'Other'
    };
    return typeNames[type] || 'Unknown';
  }

  showPrompt(message: ChatMessage): void {
    const promptText = message.prompt || 'Prompt information not available for this response.';
    
    this.dialog.open(PromptDialogComponent, {
      width: '80vw',
      maxWidth: '800px',
      maxHeight: '80vh',
      data: {
        prompt: promptText
      },
      panelClass: ['prompt-dialog-panel'],
      hasBackdrop: true,
      disableClose: false
    });
  }

  onCommentaryModeChange(enabled: boolean) {
    this.commentaryMode = enabled;
    console.log('Commentary mode changed:', enabled ? 'ON (Commentary)' : 'OFF (Q&A)');
    console.log('Current document type:', this.selectedDocumentType);
    console.log('Current commentary mode state:', this.commentaryMode);
    
    // Auto-adjust chat settings based on commentary mode
    this.adjustChatSettingsForMode(enabled);
  }

  private async adjustChatSettingsForMode(commentaryMode: boolean) {
    if (!this.currentSession?.session_id || this.selectedDocumentType !== 'performance_attribution') {
      return;
    }

    try {
      // Get current settings
      const currentSettings = await this.apiService.getSettings(this.currentSession.session_id).toPromise();
      
      // Adjust performance attribution mode in settings
      const updatedSettings = {
        ...currentSettings,
        use_rag: true,  // Always enable RAG for both modes
        prompts: {
          ...currentSettings.prompts,
          use_custom_prompts: commentaryMode  // Enable for commentary, disable for Q&A
        }
      };

      // Update settings
      await this.apiService.updateSettings(updatedSettings, this.currentSession.session_id).toPromise();
      
      console.log('Auto-updated chat settings:', {
        commentary_mode: commentaryMode,
        use_custom_prompts: updatedSettings.prompts.use_custom_prompts
      });
      
      // Show user feedback
      if (commentaryMode) {
        this.showSuccess('📊 Commentary Mode: Will generate structured attribution analysis');
      } else {
        this.showSuccess('❓ Q&A Mode: Will search documents and answer specific questions');
      }
      
    } catch (error) {
      console.error('Failed to update chat settings:', error);
      this.showError('Failed to update chat settings. Please check settings manually.');
    }
  }

  getInputPlaceholder(): string {
    if (this.selectedDocumentType === 'performance_attribution') {
      if (this.commentaryMode) {
        return 'Request attribution commentary (e.g., "Analyze Q2 2025 attribution")';
      } else {
        return 'Ask specific questions (e.g., "What was the best performing sector?")';
      }
    } else if (this.selectedDocumentType === 'vbam_support') {
      return 'Ask about VBAM features (e.g., "What is Ret Stats in IPR?", "How does Factor Attribution work?")';
    }
    return 'Ask about your financial documents...';
  }

  // Header collapse management methods
  toggleHeaderCollapse() {
    this.isHeaderCollapsed = !this.isHeaderCollapsed;
  }

  autoCollapseHeader() {
    // Auto-collapse header when there are messages and user is actively chatting
    if (this.messages.length > 2) {
      this.isHeaderCollapsed = true;
    }
  }

  expandHeaderOnNewSession() {
    // Expand header when starting a new session
    this.isHeaderCollapsed = false;
  }

  onInputFocus() {
    // Auto-collapse header when user focuses on input (if messages exist)
    if (this.messages.length > 0) {
      this.isHeaderCollapsed = true;
    }
  }

  onInputChange() {
    // Auto-collapse header when user starts typing (if messages exist)
    if (this.messages.length > 0 && this.currentMessage.trim().length > 0) {
      this.isHeaderCollapsed = true;
    }
  }
}