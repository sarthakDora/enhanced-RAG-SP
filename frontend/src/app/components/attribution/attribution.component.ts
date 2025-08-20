import { Component, OnInit, ViewChild, ElementRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import * as d3 from 'd3';
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

interface ChartData {
  title: string;
  type: 'bar' | 'line' | 'pie' | 'scatter' | 'table';
  data: any;
  description?: string;
  rawData?: any[][];
  headers?: string[];
  x_axis_title?: string;
  y_axis_title?: string;
}

interface ChartHistoryItem {
  id: string;
  title: string;
  type: string;
  prompt: string;
  data: ChartData;
  created: string;
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
  styleUrls: ['./attribution.component.css'],
  template: `
    <div class="attribution-container">
      <div class="attribution-header glass-card">
        <div>
          <h2>Performance Attribution Analysis</h2>
          <p>Upload Excel attribution files and generate professional commentary or ask specific questions</p>
        </div>
        
        <div class="header-actions">
          <button mat-icon-button 
                  [matTooltip]="'Settings'" 
                  (click)="toggleSettings()">
            <mat-icon>settings</mat-icon>
          </button>
          <button mat-icon-button 
                  [matTooltip]="'Upload File'" 
                  (click)="triggerFileInput()">
            <mat-icon>cloud_upload</mat-icon>
          </button>
        </div>
      </div>

      <!-- Collection Selection -->
      <div class="collection-selection glass-card" *ngIf="availableCollections.length > 0">
        <h4>
          <mat-icon>storage</mat-icon>
          Session Collections
        </h4>
        <p class="section-description">Switch between different attribution analysis sessions</p>
        
        <div class="collection-actions">
          <mat-form-field appearance="fill">
            <mat-label>Select Session</mat-label>
            <mat-select [(ngModel)]="selectedCollectionId"
                        (selectionChange)="onCollectionSelectionChange($event.value)">
              <mat-option *ngFor="let collection of availableCollections"
                          [value]="collection.session_id">
                {{collection.session_id}} ({{collection.points_count}} points)
              </mat-option>
            </mat-select>
          </mat-form-field>
          
          <button mat-stroked-button
                  (click)="refreshCollections()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
          
          <button mat-stroked-button
                  *ngIf="selectedCollectionId"
                  (click)="deleteSelectedCollection()">
            <mat-icon>delete</mat-icon>
            Delete
          </button>
          
          <button mat-stroked-button
                  *ngIf="selectedCollectionId"
                  (click)="switchToSession(selectedCollectionId)">
            <mat-icon>switch_account</mat-icon>
            Switch to Session
          </button>
        </div>
      </div>

      <!-- File Upload Section -->
      <div class="upload-section glass-card" *ngIf="!sessionId">
        <h3>Upload Attribution File</h3>
        <p class="section-description">Upload an Excel file containing attribution data to begin analysis</p>
        
        <div class="upload-area" 
             [class.drag-over]="isDragOver"
             (click)="triggerFileInput()"
             (dragover)="onDragOver($event)"
             (dragleave)="onDragLeave($event)"
             (drop)="onFilesDrop($event)">
          <div class="upload-content">
            <mat-icon class="upload-icon">cloud_upload</mat-icon>
            <h4 class="upload-text">Click to upload or drag Excel file here</h4>
            <p class="upload-hint">Supported formats: .xlsx, .xls, .xlsm</p>
          </div>
        </div>
        
        <input #fileInput 
               type="file" 
               (change)="onFileSelected($event)" 
               accept=".xlsx,.xls,.xlsm"
               style="display: none">
      </div>

      <!-- File Display -->
      <div class="file-display glass-card" *ngIf="uploadedFile && sessionId">
        <mat-icon>description</mat-icon>
        <div class="file-info">
          <div class="file-name">{{uploadedFile.name}}</div>
          <div class="file-details">
            {{(uploadedFile.size / 1024 / 1024).toFixed(2)}} MB • Session: {{sessionId}}
          </div>
        </div>
        <button mat-icon-button 
                [matTooltip]="'Upload new file'"
                (click)="resetSession()">
          <mat-icon>refresh</mat-icon>
        </button>
      </div>

      <!-- Chunks Display -->
      <div class="chunks-section glass-card" *ngIf="chunkList.length > 0">
        <h3>Data Chunks</h3>
        <p class="section-description">{{chunkList.length}} chunks of attribution data processed</p>
        
        <div class="chunks-list">
          <mat-chip-listbox>
            <mat-chip *ngFor="let chunk of chunkList; let i = index" 
                     [value]="i">
              <mat-icon matChipAvatar>{{chunk.document_type === 'equity' ? 'trending_up' : 'account_balance'}}</mat-icon>
              {{chunk.filename}} - {{chunk.chunk_type}}
            </mat-chip>
          </mat-chip-listbox>
        </div>
      </div>
      
      <!-- Main Content Tabs -->
      <mat-tab-group class="glass-card" *ngIf="sessionId" dynamicHeight>
        <!-- Commentary Tab - FIRST -->
        <mat-tab label="Professional Commentary">
          <div class="tab-content">
            <div class="mode-description">
              <mat-icon>description</mat-icon>
              <div>
                <h4>Professional Attribution Commentary</h4>
                <p>Generate institutional-grade performance attribution commentary for your reports and presentations.</p>
              </div>
            </div>

            <div class="commentary-interface">
              <h3>Generate Commentary</h3>
              <p class="section-description">Create professional attribution analysis for client reports</p>
              
              <div class="commentary-row">
                <mat-form-field appearance="fill" class="period-input">
                  <mat-label>Period (optional)</mat-label>
                  <input matInput 
                         [(ngModel)]="commentaryPeriod"
                         placeholder="e.g., Q3 2024, YTD 2024">
                </mat-form-field>
                
                <button mat-raised-button 
                        class="generate-commentary-button"
                        [disabled]="isGeneratingCommentary"
                        (click)="generateCommentary()">
                  <mat-icon *ngIf="!isGeneratingCommentary">article</mat-icon>
                  <mat-icon *ngIf="isGeneratingCommentary" class="spinning">refresh</mat-icon>
                  {{ isGeneratingCommentary ? 'Generating...' : 'Generate Commentary' }}
                </button>
              </div>

              <!-- Commentary Output -->
              <div class="commentary-output" *ngIf="currentCommentary">
                <div class="commentary-header">
                  <h4>
                    <mat-icon>article</mat-icon>
                    Generated Commentary
                  </h4>
                  <div class="commentary-actions">
                    <button mat-icon-button [matTooltip]="'Copy to Clipboard'" (click)="copyCommentary()">
                      <mat-icon>content_copy</mat-icon>
                    </button>
                    <button mat-icon-button [matTooltip]="'Download as Word'" (click)="downloadCommentary()">
                      <mat-icon>download</mat-icon>
                    </button>
                  </div>
                </div>
                <div class="commentary-content" [innerHTML]="currentCommentary"></div>
              </div>

              <!-- Progress Indicator -->
              <div class="progress-indicator" *ngIf="isGeneratingCommentary">
                <mat-progress-bar mode="indeterminate"></mat-progress-bar>
                <p class="progress-text">Generating professional commentary...</p>
                <p class="progress-detail">Analyzing attribution data and creating institutional-grade analysis</p>
              </div>
            </div>
          </div>
        </mat-tab>

        <!-- Q&A Tab -->
        <mat-tab label="Attribution Q&A">
          <div class="tab-content">
            <div class="mode-description">
              <mat-icon>quiz</mat-icon>
              <div>
                <h4>Interactive Attribution Analysis</h4>
                <p>Ask specific questions about your attribution data and get detailed answers based on the actual data in your uploaded file.</p>
              </div>
            </div>

            <div class="qa-interface">
              <h3>Ask Questions</h3>
              <p class="section-description">Get answers based on your attribution data</p>
              
              <div class="qa-row">
                <div class="question-input">
                  <mat-form-field appearance="fill">
                    <mat-label>Ask a question about your attribution data</mat-label>
                    <textarea matInput 
                              [(ngModel)]="currentQuestion"
                              placeholder="e.g., 'What were the top 3 contributors by total attribution?'"
                              rows="2"
                              (keydown.enter)="handleKeydown($event)"></textarea>
                    <mat-hint>Ask specific questions about performance, allocation, selection effects, etc.</mat-hint>
                  </mat-form-field>
                </div>
                
                <button mat-raised-button 
                        class="ask-question-button"
                        [disabled]="isAskingQuestion || !currentQuestion.trim()"
                        (click)="askQuestion()">
                  <mat-icon *ngIf="!isAskingQuestion">help</mat-icon>
                  <mat-icon *ngIf="isAskingQuestion" class="spinning">refresh</mat-icon>
                  {{ isAskingQuestion ? 'Analyzing...' : 'Ask Question' }}
                </button>
              </div>

              <!-- Sample Questions -->
              <div class="sample-questions">
                <h5>Sample Questions</h5>
                <p class="section-description">Click any question to try it out</p>
                <div class="questions-grid">
                  <button *ngFor="let question of sampleQuestions" 
                          class="sample-question"
                          (click)="useQuestion(question)">
                    {{question}}
                  </button>
                </div>
              </div>

              <!-- Q&A Response -->
              <div class="qa-response" *ngIf="currentResponse">
                <div class="response-header">
                  <h4>
                    <mat-icon>psychology</mat-icon>
                    Answer
                  </h4>
                </div>
                <div class="response-content">{{currentResponse}}</div>
              </div>

              <!-- Progress Indicator -->
              <div class="progress-indicator" *ngIf="isAskingQuestion">
                <mat-progress-bar mode="indeterminate"></mat-progress-bar>
                <p class="progress-text">Analyzing your data to answer the question...</p>
                <p class="progress-detail">This may take a few moments for complex queries</p>
              </div>
            </div>
          </div>
        </mat-tab>

        <!-- Visualization Tab -->
        <mat-tab label="Data Visualization">
          <div class="tab-content">
            <div class="mode-description">
              <mat-icon>analytics</mat-icon>
              <div>
                <h4>AI-Powered Data Visualization</h4>
                <p>Generate interactive charts from your attribution data using natural language prompts. Describe what you want to visualize and let AI create the perfect chart for your analysis.</p>
              </div>
            </div>

            <div class="visualization-interface">
              <h3>Create Visualization</h3>
              <p class="section-description">Describe the chart you want to create using natural language</p>
              
              <div class="visualization-row">
                <div class="prompt-input">
                  <mat-form-field appearance="fill">
                    <mat-label>Describe your visualization</mat-label>
                    <textarea matInput 
                              [(ngModel)]="currentPrompt"
                              placeholder="e.g., 'Create a bar chart showing total attribution by country'"
                              rows="2"
                              (keydown.enter)="handleKeydown($event)"></textarea>
                    <mat-hint>Tip: Be specific about chart type, data, and sorting preferences</mat-hint>
                  </mat-form-field>
                </div>
                
                <button mat-raised-button 
                        class="generate-chart-button"
                        [disabled]="isGeneratingChart || !currentPrompt.trim()"
                        (click)="generateChart()">
                  <mat-icon *ngIf="!isGeneratingChart">auto_graph</mat-icon>
                  <mat-icon *ngIf="isGeneratingChart" class="spinning">refresh</mat-icon>
                  {{ isGeneratingChart ? 'Generating...' : 'Generate Chart' }}
                </button>
              </div>

              <!-- Sample Prompts -->
              <div class="sample-prompts">
                <h5>Sample Visualization Prompts</h5>
                <p class="section-description">Click any prompt to try it out</p>
                <div class="prompts-grid">
                  <button *ngFor="let prompt of samplePrompts" 
                          class="sample-prompt"
                          (click)="usePrompt(prompt)">
                    {{prompt}}
                  </button>
                </div>
              </div>
            </div>

            <!-- Chart Display -->
            <div class="chart-display" *ngIf="currentChart">
              <div class="chart-header">
                <h4>
                  <mat-icon>{{ getChartIcon(currentChart.type) }}</mat-icon>
                  {{ currentChart.title }}
                </h4>
                
                <div class="chart-actions">
                  <button mat-icon-button 
                          [matTooltip]="'Download Chart'"
                          (click)="downloadChart()">
                    <mat-icon>download</mat-icon>
                  </button>
                  <button mat-icon-button 
                          [matTooltip]="'Fullscreen View'"
                          (click)="toggleFullscreen()">
                    <mat-icon>fullscreen</mat-icon>
                  </button>
                </div>
              </div>
              
              <div class="chart-container" 
                   #chartContainer 
                   [class.fullscreen-chart]="isFullscreen">
                <div class="chart-controls" *ngIf="currentChart">
                  <button class="chart-btn download-btn" 
                          (click)="downloadChart()"
                          [matTooltip]="'Download as PNG'">
                    📥
                  </button>
                  <button class="chart-btn fullscreen-btn" 
                          (click)="toggleFullscreen()"
                          [matTooltip]="isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'">
                    {{ isFullscreen ? '🗗' : '🗖' }}
                  </button>
                </div>
                
                <div class="d3-chart-wrapper" #d3Container></div>
              </div>
              
              <div *ngIf="currentChart.description" class="chart-description">
                <p>{{ currentChart.description }}</p>
              </div>
            </div>

            <!-- Progress Indicator -->
            <div class="progress-indicator" *ngIf="isGeneratingChart">
              <mat-progress-bar mode="indeterminate"></mat-progress-bar>
              <p class="progress-text">Analyzing your data and generating visualization...</p>
              <p class="progress-detail">This may take a few moments for complex datasets</p>
            </div>
          </div>
        </mat-tab>
      </mat-tab-group>

      <!-- No Data Message -->
      <div class="no-data-message glass-card" *ngIf="!sessionId && !isLoading">
        <mat-icon>cloud_upload</mat-icon>
        <div class="no-data-title">Upload a File to Get Started</div>
        <div class="no-data-subtitle">Upload an Excel attribution file to begin creating visualizations from your data</div>
      </div>
    </div>
  `
})
export class AttributionComponent implements OnInit {
  @ViewChild('fileInput') fileInput!: ElementRef;
  @ViewChild('chartContainer') chartContainer!: ElementRef;
  @ViewChild('d3Container') d3Container!: ElementRef;

  chunkList: any[] = [];
  sessionId: string | null = null;
  isLoading = false;
  isGeneratingChart = false;
  currentChart: ChartData | null = null;
  uploadedFile: File | null = null;
  
  currentPrompt = '';
  currentQuestion = '';
  currentResponse: string | null = null;
  currentCommentary: string | null = null;
  commentaryPeriod = '';
  preferredChartType: string | null = null;
  
  availableCollections: CollectionInfo[] = [];
  selectedCollectionId: string | null = null;
  
  isDragOver = false;
  isFullscreen = false;
  isAskingQuestion = false;
  isGeneratingCommentary = false;

  samplePrompts = [
    // Bar Charts
    'Create a bar chart showing total attribution by country',
    'Show allocation effects by sector in descending order',
    'Display selection effects ranked from highest to lowest',
    'Generate a bar chart of currency effects by country',
    'Plot carry effects by sector, ordered by magnitude',
    'Create a horizontal bar chart of position weights vs benchmark',
    'Show top 10 contributors and bottom 5 detractors in one chart',
    'Display FX effects vs carry effects side by side by country',
    'Generate a stacked bar chart showing attribution breakdown by component',
    'Create a grouped bar chart comparing portfolio vs benchmark returns',
    
    // Line Charts
    'Create a line chart tracking attribution trends over time',
    'Show the cumulative attribution effect progression',
    'Display portfolio performance vs benchmark over time',
    'Generate a trend line of allocation effects by month',
    'Plot the evolution of sector weights over the period',
    'Create a time series of total return attribution',
    
    // Scatter Plots
    'Create a scatter plot of allocation vs selection effects',
    'Plot sector weights vs attribution contribution',
    'Show the relationship between benchmark weight and active weight',
    'Display selection effect vs allocation effect by position',
    'Generate a scatter plot of carry vs FX effects',
    'Plot allocation effects vs benchmark weights as scatter points',
    
    // Pie Charts
    'Show a pie chart of allocation effects by country',
    'Create a pie chart showing attribution breakdown by component type',
    'Display a pie chart of positive contributors vs negative detractors',
    'Generate a pie chart of sector allocation distribution',
    
    // Tables
    'Create a table ranking all positions by total attribution',
    'Generate a detailed table showing all attribution components by country',
    'Display a summary table of top performers and worst performers',
    'Create a comprehensive attribution table with all metrics'
  ];

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
    this.loadAvailableCollections();
  }

  toggleSettings() {
    const dialogRef = this.dialog.open(ChatSettingsDialogComponent, {
      width: '500px',
      data: { component: 'attribution' }
    });
  }

  triggerFileInput() {
    this.fileInput.nativeElement.click();
  }

  onFileSelected(event: any) {
    const file = event.target.files?.[0];
    if (file) {
      this.uploadFile(file);
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

  onFilesDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
    
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.uploadFile(files[0]);
    }
  }

  async uploadFile(file: File) {
    this.isLoading = true;
    this.uploadedFile = file;
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      formData.append('session_id', sessionId);
      
      const response = await this.apiService.uploadAttributionFile(formData).toPromise();
      
      if (response?.session_id) {
        this.sessionId = response.session_id;
        this.chunkList = response.chunks || [];
        
        this.snackBar.open(`File uploaded successfully! Created ${response.chunks_created || 0} data chunks.`, 'Close', {
          duration: 3000
        });
        
        await this.loadAvailableCollections();
      }
    } catch (error: any) {
      console.error('Error uploading file:', error);
      this.snackBar.open(`Upload failed: ${error.error?.detail || error.message}`, 'Close', {
        duration: 5000
      });
      this.uploadedFile = null;
    } finally {
      this.isLoading = false;
    }
  }

  async loadAvailableCollections() {
    try {
      const response = await this.apiService.getAttributionCollections().toPromise();
      this.availableCollections = response?.collections || [];
    } catch (error) {
      console.error('Error loading collections:', error);
    }
  }

  onCollectionSelectionChange(sessionId: string) {
    this.selectedCollectionId = sessionId;
  }

  async refreshCollections() {
    await this.loadAvailableCollections();
    this.snackBar.open('Collections refreshed', 'Close', { duration: 2000 });
  }

  async deleteSelectedCollection() {
    if (!this.selectedCollectionId) return;
    
    try {
      await this.apiService.clearAttributionSession(this.selectedCollectionId).toPromise();
      this.snackBar.open('Collection deleted successfully', 'Close', { duration: 2000 });
      await this.loadAvailableCollections();
      this.selectedCollectionId = null;
    } catch (error) {
      console.error('Error deleting collection:', error);
      this.snackBar.open('Failed to delete collection', 'Close', { duration: 3000 });
    }
  }

  switchToSession(sessionId: string) {
    this.sessionId = sessionId;
    this.currentChart = null;
    this.snackBar.open(`Switched to session: ${sessionId}`, 'Close', { duration: 2000 });
  }

  resetSession() {
    this.sessionId = null;
    this.uploadedFile = null;
    this.currentChart = null;
    this.currentPrompt = '';
    this.chunkList = [];
  }

  usePrompt(prompt: string) {
    this.currentPrompt = prompt;
  }

  useQuestion(question: string) {
    this.currentQuestion = question;
  }

  handleKeydown(event: Event) {
    const keyboardEvent = event as KeyboardEvent;
    if (keyboardEvent.ctrlKey) {
      if (this.currentQuestion && this.currentQuestion.trim()) {
        this.askQuestion();
      } else if (this.currentPrompt && this.currentPrompt.trim()) {
        this.generateChart();
      }
    }
  }

  async askQuestion() {
    if (!this.sessionId || !this.currentQuestion.trim()) {
      this.snackBar.open('Please upload a file and enter a question first', 'Close', { duration: 3000 });
      return;
    }

    this.isAskingQuestion = true;
    this.currentResponse = null;
    
    try {
      const formData = new FormData();
      formData.append('session_id', this.sessionId);
      formData.append('question', this.currentQuestion.trim());
      formData.append('mode', 'qa');

      const response = await this.apiService.askAttributionQuestion(formData).toPromise();
      
      if (response && response.response) {
        this.currentResponse = response.response;
        this.snackBar.open('Question answered successfully!', 'Close', { duration: 3000 });
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error: any) {
      console.error('Error asking question:', error);
      this.snackBar.open(`Failed to answer question: ${error.error?.detail || error.message}`, 'Close', {
        duration: 5000
      });
    } finally {
      this.isAskingQuestion = false;
    }
  }

  async generateCommentary() {
    if (!this.sessionId) {
      this.snackBar.open('Please upload a file first', 'Close', { duration: 3000 });
      return;
    }

    this.isGeneratingCommentary = true;
    this.currentCommentary = null;
    
    try {
      const formData = new FormData();
      formData.append('session_id', this.sessionId);
      if (this.commentaryPeriod && this.commentaryPeriod.trim()) {
        formData.append('period', this.commentaryPeriod.trim());
      }

      const response = await this.apiService.generateAttributionCommentary(formData).toPromise();
      
      if (response && response.response) {
        this.currentCommentary = response.response;
        this.snackBar.open('Commentary generated successfully!', 'Close', { duration: 3000 });
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error: any) {
      console.error('Error generating commentary:', error);
      this.snackBar.open(`Failed to generate commentary: ${error.error?.detail || error.message}`, 'Close', {
        duration: 5000
      });
    } finally {
      this.isGeneratingCommentary = false;
    }
  }

  copyCommentary() {
    if (this.currentCommentary) {
      navigator.clipboard.writeText(this.currentCommentary).then(() => {
        this.snackBar.open('Commentary copied to clipboard!', 'Close', { duration: 2000 });
      });
    }
  }

  downloadCommentary() {
    if (this.currentCommentary) {
      const blob = new Blob([this.currentCommentary], { type: 'text/plain' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `attribution-commentary-${new Date().toISOString().split('T')[0]}.txt`;
      link.click();
      window.URL.revokeObjectURL(url);
    }
  }

  async generateChart() {
    if (!this.sessionId || !this.currentPrompt.trim()) {
      this.snackBar.open('Please upload a file and enter a prompt first', 'Close', { duration: 3000 });
      return;
    }

    this.isGeneratingChart = true;
    
    try {
      const formData = new FormData();
      formData.append('session_id', this.sessionId);
      formData.append('prompt', this.currentPrompt.trim());
      
      // Always append chart_type, even if empty (for auto-detect)
      formData.append('chart_type', this.preferredChartType || '');

      const response = await this.apiService.generateAttributionVisualization(formData).toPromise();
      
      if (response && response.data) {
        this.currentChart = {
          title: response.title || 'Generated Chart',
          type: response.type || 'bar',
          data: response.data,
          description: response.description,
          rawData: response.raw_data,
          headers: response.headers
        };
        
        // Render the chart after a brief delay to ensure DOM is ready
        setTimeout(() => {
          this.renderChart();
        }, 100);
        
        this.snackBar.open('Chart generated successfully!', 'Close', { duration: 3000 });
      } else {
        throw new Error('Invalid response from server');
      }
    } catch (error: any) {
      console.error('Error generating chart:', error);
      this.snackBar.open(`Failed to generate chart: ${error.error?.detail || error.message}`, 'Close', {
        duration: 5000
      });
    } finally {
      this.isGeneratingChart = false;
    }
  }

  renderChart() {
    if (!this.currentChart || !this.d3Container) return;

    // Clear previous chart
    d3.select(this.d3Container.nativeElement).selectAll('*').remove();

    switch (this.currentChart.type) {
      case 'bar':
        this.renderD3BarChart();
        break;
      case 'line':
        this.renderD3LineChart();
        break;
      case 'scatter':
        this.renderD3ScatterChart();
        break;
      case 'pie':
        this.renderD3PieChart();
        break;
      default:
        console.warn('Unsupported chart type:', this.currentChart.type);
    }
  }

  renderD3BarChart() {
    if (!this.currentChart?.data?.datasets?.[0]?.data) return;

    const container = d3.select(this.d3Container.nativeElement);
    const containerRect = this.d3Container.nativeElement.getBoundingClientRect();
    
    const margin = { top: 40, right: 40, bottom: 60, left: 80 };
    const width = containerRect.width - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = container.append('svg')
      .attr('width', containerRect.width)
      .attr('height', 400);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const dataset = this.currentChart.data.datasets[0];
    const labels = this.currentChart.data.labels || [];
    const data = dataset.data.map((value: number, index: number) => ({
      label: labels[index] || `Item ${index + 1}`,
      value: typeof value === 'number' ? value : 0
    }));

    const xScale = d3.scaleBand()
      .domain(data.map((d: any) => d.label))
      .range([0, width])
      .padding(0.1);

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data, (d: any) => d.value) as unknown as [number, number])
      .nice()
      .range([height, 0]);

    // Add axes
    g.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .style('text-anchor', 'end')
      .attr('dx', '-.8em')
      .attr('dy', '.15em')
      .attr('transform', 'rotate(-45)')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    g.append('g')
      .call(d3.axisLeft(yScale))
      .selectAll('text')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    // Add bars with animation
    g.selectAll('.bar')
      .data(data)
      .enter().append('rect')
      .attr('class', 'bar')
      .attr('x', (d: any) => xScale(d.label)!)
      .attr('width', xScale.bandwidth())
      .attr('y', height)
      .attr('height', 0)
      .style('fill', (d, i) => d3.schemeCategory10[i % 10])
      .style('opacity', 0.8)
      .transition()
      .duration(800)
      .ease(d3.easeElastic)
      .attr('y', (d: any) => yScale(d.value))
      .attr('height', (d: any) => height - yScale(d.value));

    // Add hover effects
    g.selectAll('.bar')
      .on('mouseover', function(event, d) {
        d3.select(this).style('opacity', 1).style('stroke', '#fff').style('stroke-width', 2);
      })
      .on('mouseout', function(event, d) {
        d3.select(this).style('opacity', 0.8).style('stroke', 'none');
      });
  }

  renderD3LineChart() {
    if (!this.currentChart?.data?.datasets?.[0]?.data) return;

    const container = d3.select(this.d3Container.nativeElement);
    const containerRect = this.d3Container.nativeElement.getBoundingClientRect();
    
    const margin = { top: 40, right: 40, bottom: 60, left: 80 };
    const width = containerRect.width - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = container.append('svg')
      .attr('width', containerRect.width)
      .attr('height', 400);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const dataset = this.currentChart.data.datasets[0];
    const labels = this.currentChart.data.labels || [];
    const data = dataset.data.map((value: number, index: number) => ({
      x: index,
      y: typeof value === 'number' ? value : 0,
      label: labels[index] || `Point ${index + 1}`
    }));

    const xScale = d3.scaleLinear()
      .domain(d3.extent(data, (d: any) => d.x) as unknown as [number, number])
      .range([0, width]);

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data, (d: any) => d.y) as unknown as [number, number])
      .nice()
      .range([height, 0]);

    const line = d3.line<any>()
      .x(d => xScale(d.x))
      .y(d => yScale(d.y))
      .curve(d3.curveMonotoneX);

    // Add axes
    g.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    g.append('g')
      .call(d3.axisLeft(yScale))
      .selectAll('text')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    // Add line with animation
    const path = g.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#42a5f5')
      .attr('stroke-width', 3)
      .attr('d', line);

    const totalLength = path.node()!.getTotalLength();
    path.attr('stroke-dasharray', totalLength + ' ' + totalLength)
      .attr('stroke-dashoffset', totalLength)
      .transition()
      .duration(1500)
      .ease(d3.easeLinear)
      .attr('stroke-dashoffset', 0);

    // Add dots
    g.selectAll('.dot')
      .data(data)
      .enter().append('circle')
      .attr('class', 'dot')
      .attr('cx', (d: any) => xScale(d.x))
      .attr('cy', (d: any) => yScale(d.y))
      .attr('r', 0)
      .style('fill', '#42a5f5')
      .transition()
      .delay((d, i) => i * 100)
      .duration(500)
      .attr('r', 5);
  }

  renderD3ScatterChart() {
    if (!this.currentChart?.data?.datasets?.[0]?.data) return;

    const container = d3.select(this.d3Container.nativeElement);
    const containerRect = this.d3Container.nativeElement.getBoundingClientRect();
    
    const margin = { top: 40, right: 40, bottom: 60, left: 80 };
    const width = containerRect.width - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;

    const svg = container.append('svg')
      .attr('width', containerRect.width)
      .attr('height', 400);

    const g = svg.append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    const dataset = this.currentChart.data.datasets[0];
    const data = dataset.data.map((point: any, index: number) => ({
      x: point.x || index,
      y: point.y || point,
      label: point.label || `Point ${index + 1}`
    }));

    const xScale = d3.scaleLinear()
      .domain(d3.extent(data, (d: any) => d.x) as unknown as [number, number])
      .nice()
      .range([0, width]);

    const yScale = d3.scaleLinear()
      .domain(d3.extent(data, (d: any) => d.y) as unknown as [number, number])
      .nice()
      .range([height, 0]);

    // Add axes
    g.append('g')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(xScale))
      .selectAll('text')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    g.append('g')
      .call(d3.axisLeft(yScale))
      .selectAll('text')
      .style('fill', 'rgba(255, 255, 255, 0.8)');

    // Add dots with animation
    g.selectAll('.dot')
      .data(data)
      .enter().append('circle')
      .attr('class', 'dot')
      .attr('cx', (d: any) => xScale(d.x))
      .attr('cy', (d: any) => yScale(d.y))
      .attr('r', 0)
      .style('fill', (d, i) => d3.schemeCategory10[i % 10])
      .style('opacity', 0.7)
      .transition()
      .delay((d, i) => i * 50)
      .duration(500)
      .attr('r', 6);
  }

  renderD3PieChart() {
    if (!this.currentChart?.data?.datasets?.[0]?.data) return;

    const container = d3.select(this.d3Container.nativeElement);
    const containerRect = this.d3Container.nativeElement.getBoundingClientRect();
    
    const width = containerRect.width;
    const height = 400;
    const radius = Math.min(width, height) / 2 - 40;

    const svg = container.append('svg')
      .attr('width', width)
      .attr('height', height);

    const g = svg.append('g')
      .attr('transform', `translate(${width / 2},${height / 2})`);

    const dataset = this.currentChart.data.datasets[0];
    const labels = this.currentChart.data.labels || [];
    const data = dataset.data.map((value: number, index: number) => ({
      label: labels[index] || `Slice ${index + 1}`,
      value: typeof value === 'number' ? Math.abs(value) : 0
    }));

    const pie = d3.pie<any>().value(d => d.value);
    const arc = d3.arc<any>().innerRadius(0).outerRadius(radius);

    const arcs = g.selectAll('.arc')
      .data(pie(data))
      .enter().append('g')
      .attr('class', 'arc');

    arcs.append('path')
      .attr('d', arc)
      .style('fill', (d, i) => d3.schemeCategory10[i % 10])
      .style('opacity', 0.8)
      .transition()
      .duration(1000)
      .attrTween('d', function(d: any) {
        const i = d3.interpolate({startAngle: 0, endAngle: 0}, d);
        return function(t: number) { return arc(i(t)) || ''; };
      });

    // Add labels
    arcs.append('text')
      .attr('transform', d => `translate(${arc.centroid(d)})`)
      .attr('dy', '.35em')
      .style('text-anchor', 'middle')
      .style('fill', 'white')
      .style('font-size', '12px')
      .text(d => d.data.label);
  }

  getChartIcon(type: string): string {
    switch (type) {
      case 'bar': return 'bar_chart';
      case 'line': return 'show_chart';
      case 'pie': return 'pie_chart';
      case 'scatter': return 'scatter_plot';
      case 'table': return 'table_chart';
      default: return 'analytics';
    }
  }

  downloadChart() {
    if (!this.d3Container) return;

    const svg = this.d3Container.nativeElement.querySelector('svg');
    if (!svg) return;

    const svgData = new XMLSerializer().serializeToString(svg);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d')!;
    
    const img = new Image();
    img.onload = () => {
      canvas.width = img.width;
      canvas.height = img.height;
      ctx.fillStyle = '#1a1a1a';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0);
      
      const link = document.createElement('a');
      link.download = `${this.currentChart?.title || 'chart'}.png`;
      link.href = canvas.toDataURL();
      link.click();
    };
    
    img.src = 'data:image/svg+xml;base64,' + btoa(svgData);
  }

  toggleFullscreen() {
    this.isFullscreen = !this.isFullscreen;
    
    setTimeout(() => {
      this.renderChart();
    }, 100);
  }
}