import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = environment.apiUrl || 'http://localhost:8000/api';
  private connectionStatus = new BehaviorSubject<boolean>(true);
  private documentsUpdated = new BehaviorSubject<boolean>(false);

  constructor(private http: HttpClient) {
    this.checkHealth();
  }

  get connectionStatus$() {
    return this.connectionStatus.asObservable();
  }

  get documentsUpdated$() {
    return this.documentsUpdated.asObservable();
  }

  notifyDocumentsUpdated() {
    this.documentsUpdated.next(true);
  }

  private getHeaders(): HttpHeaders {
    return new HttpHeaders({
      'Content-Type': 'application/json'
    });
  }

  // Health Check
  checkHealth(): Observable<any> {
    return this.http.get(`${this.baseUrl}/health`);
  }

  // Document API
  uploadDocuments(files: File[], documentType: string, tags: string): Observable<any> {
    const formData = new FormData();
    
    files.forEach(file => {
      formData.append('files', file);
    });
    
    formData.append('document_type', documentType);
    if (tags) {
      formData.append('tags', tags);
    }

    return this.http.post(`${this.baseUrl}/documents/upload`, formData).pipe(
      tap(() => this.notifyDocumentsUpdated())
    );
  }

  searchDocuments(searchRequest: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/documents/search`, searchRequest, {
      headers: this.getHeaders()
    });
  }

  getDocuments(): Observable<any> {
    return this.http.get(`${this.baseUrl}/documents/list`);
  }

  getDocument(documentId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/documents/${documentId}`);
  }

  deleteDocument(documentId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/documents/${documentId}`).pipe(
      tap(() => this.notifyDocumentsUpdated())
    );
  }

  getDocumentStats(): Observable<any> {
    return this.http.get(`${this.baseUrl}/documents/stats/overview`);
  }

  // Chat API
  sendMessage(chatRequest: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/chat/message`, chatRequest, {
      headers: this.getHeaders()
    });
  }

  createSession(title?: string, documentType?: string): Observable<any> {
    const body: any = {};
    if (title) body.title = title;
    if (documentType) body.document_type = documentType;
    
    return this.http.post(`${this.baseUrl}/chat/sessions`, body, {
      headers: this.getHeaders()
    });
  }

  getSessions(limit: number = 50): Observable<any> {
    const params = new HttpParams().set('limit', limit.toString());
    return this.http.get(`${this.baseUrl}/chat/sessions`, { params });
  }

  getSession(sessionId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/chat/sessions/${sessionId}`);
  }

  getChatHistory(sessionId: string, limit: number = 50, offset: number = 0): Observable<any> {
    const params = new HttpParams()
      .set('limit', limit.toString())
      .set('offset', offset.toString());
    
    return this.http.get(`${this.baseUrl}/chat/sessions/${sessionId}/history`, { params });
  }

  deleteSession(sessionId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/chat/sessions/${sessionId}`);
  }

  updateSessionTitle(sessionId: string, title: string): Observable<any> {
    const params = new HttpParams().set('title', title);
    return this.http.post(`${this.baseUrl}/chat/sessions/${sessionId}/title`, null, { params });
  }

  // Clear documents by category/type
  clearDocumentsByCategory(documentType: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/documents/clear-category/${documentType}`, {}, {
      headers: this.getHeaders()
    }).pipe(
      tap(() => this.notifyDocumentsUpdated())
    );
  }

  // Health monitoring
  private checkConnectionStatus() {
    this.checkHealth().subscribe({
      next: () => this.connectionStatus.next(true),
      error: () => this.connectionStatus.next(false)
    });
  }

  startHealthMonitoring() {
    // Check connection status every 30 seconds
    setInterval(() => {
      this.checkConnectionStatus();
    }, 30000);
  }

  // Settings API
  getSettings(sessionId?: string): Observable<any> {
    let params = new HttpParams();
    if (sessionId) {
      params = params.set('session_id', sessionId);
    }
    return this.http.get(`${this.baseUrl}/settings`, { params });
  }

  updateSettings(settings: any, sessionId?: string): Observable<any> {
    let params = new HttpParams();
    if (sessionId) {
      params = params.set('session_id', sessionId);
    }
    return this.http.post(`${this.baseUrl}/settings`, settings, { 
      params,
      headers: this.getHeaders() 
    });
  }

  getDefaultPrompts(): Observable<any> {
    return this.http.get(`${this.baseUrl}/settings/prompts/defaults`);
  }

  // Attribution API
  uploadAttributionFile(formData: FormData): Observable<any> {
    return this.http.post(`${this.baseUrl}/attribution/upload`, formData);
  }

  askAttributionQuestion(formData: FormData): Observable<any> {
    return this.http.post(`${this.baseUrl}/attribution/question`, formData);
  }

  generateAttributionCommentary(formData: FormData): Observable<any> {
    return this.http.post(`${this.baseUrl}/attribution/commentary`, formData);
  }

  getAttributionSessionStats(sessionId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/attribution/session/${sessionId}/stats`);
  }

  clearAttributionSession(sessionId: string): Observable<any> {
    return this.http.delete(`${this.baseUrl}/attribution/session/${sessionId}`);
  }

  getAttributionHealth(): Observable<any> {
    return this.http.get(`${this.baseUrl}/attribution/health`);
  }

  getAttributionExamples(): Observable<any> {
    return this.http.get(`${this.baseUrl}/attribution/examples`);
  }

  getAttributionCollections(): Observable<any> {
    return this.http.get(`${this.baseUrl}/attribution/collections`);
  }

  generateAttributionVisualization(formData: FormData): Observable<any> {
    return this.http.post(`${this.baseUrl}/attribution/viz-working`, formData);
  }

  // VBAM Component API
  initializeVBAMCollections(): Observable<any> {
    return this.http.post(`${this.baseUrl}/vbam/initialize`, {});
  }

  createVBAMSampleData(): Observable<any> {
    return this.http.post(`${this.baseUrl}/vbam/sample-data`, {});
  }

  uploadVBAMDocument(component: string, file: File, description?: string): Observable<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (description) {
      formData.append('description', description);
    }
    // Don't set Content-Type header for FormData - let browser set it with boundary
    return this.http.post(`${this.baseUrl}/vbam/upload/${component}`, formData);
  }

  askVBAMQuestion(question: string, component?: string): Observable<any> {
    const payload: any = { question };
    if (component) {
      payload.component = component;
    }
    return this.http.post(`${this.baseUrl}/vbam/ask`, payload, {
      headers: this.getHeaders()
    });
  }

  searchVBAMComponent(component: string, question: string, topK: number = 10): Observable<any> {
    const payload = { question, top_k: topK };
    return this.http.post(`${this.baseUrl}/vbam/search/${component}`, payload, {
      headers: this.getHeaders()
    });
  }

  routeVBAMQuestion(question: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/vbam/route`, { question }, {
      headers: this.getHeaders()
    });
  }

  getVBAMComponents(): Observable<any> {
    return this.http.get(`${this.baseUrl}/vbam/components`);
  }

  getVBAMStats(): Observable<any> {
    return this.http.get(`${this.baseUrl}/vbam/stats`);
  }

  // Generic API methods for flexibility
  get(endpoint: string): Promise<any> {
    return this.http.get(`${this.baseUrl}${endpoint}`).toPromise() as Promise<any>;
  }

  post(endpoint: string, data?: any): Promise<any> {
    return this.http.post(`${this.baseUrl}${endpoint}`, data, {
      headers: this.getHeaders()
    }).toPromise() as Promise<any>;
  }

  put(endpoint: string, data?: any): Promise<any> {
    return this.http.put(`${this.baseUrl}${endpoint}`, data, {
      headers: this.getHeaders()
    }).toPromise() as Promise<any>;
  }

  delete(endpoint: string): Promise<any> {
    return this.http.delete(`${this.baseUrl}${endpoint}`).toPromise() as Promise<any>;
  }
}