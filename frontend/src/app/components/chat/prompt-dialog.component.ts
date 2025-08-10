import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatDialogRef, MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-prompt-dialog',
  standalone: true,
  imports: [CommonModule, MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <div class="prompt-dialog">
      <div mat-dialog-title class="dialog-title">
        <mat-icon>code</mat-icon>
        <span>Prompt Sent to LLM</span>
        <button mat-icon-button 
                mat-dialog-close
                class="close-button">
          <mat-icon>close</mat-icon>
        </button>
      </div>
      
      <div mat-dialog-content class="dialog-content">
        <div class="prompt-content">
          <pre>{{ data.prompt }}</pre>
        </div>
      </div>
      
      <div mat-dialog-actions class="dialog-actions">
        <button mat-button mat-dialog-close color="primary">Close</button>
        <button mat-button (click)="copyToClipboard()" color="accent">
          <mat-icon>content_copy</mat-icon>
          Copy
        </button>
      </div>
    </div>
  `,
  styles: [`
    .prompt-dialog {
      width: 80vw;
      max-width: 800px;
      max-height: 80vh;
    }

    .dialog-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 18px;
      font-weight: 600;
      margin-bottom: 16px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding-bottom: 12px;
    }

    .close-button {
      margin-left: auto;
    }

    .dialog-content {
      padding: 0;
    }

    .prompt-content {
      background: rgba(0, 0, 0, 0.3);
      border-radius: 8px;
      padding: 16px;
      max-height: 500px;
      overflow-y: auto;
      margin-bottom: 16px;
    }

    .prompt-content pre {
      margin: 0;
      white-space: pre-wrap;
      word-wrap: break-word;
      font-family: 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.4;
      color: var(--text-primary);
    }

    .dialog-actions {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      padding-top: 16px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Custom scrollbar for the prompt content */
    .prompt-content::-webkit-scrollbar {
      width: 6px;
    }

    .prompt-content::-webkit-scrollbar-track {
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
    }

    .prompt-content::-webkit-scrollbar-thumb {
      background: rgba(255, 255, 255, 0.3);
      border-radius: 3px;
    }

    .prompt-content::-webkit-scrollbar-thumb:hover {
      background: rgba(255, 255, 255, 0.5);
    }
  `]
})
export class PromptDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<PromptDialogComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { prompt: string }
  ) {}

  copyToClipboard(): void {
    navigator.clipboard.writeText(this.data.prompt).then(() => {
      // You could show a snackbar here to confirm copy
      console.log('Prompt copied to clipboard');
    }).catch(err => {
      console.error('Failed to copy prompt: ', err);
    });
  }
}