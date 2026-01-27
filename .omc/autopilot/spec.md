# Task Management REST API - Specification

## Requirements Summary

### Functional Requirements
- CRUD operations for tasks (create, read, update, delete)
- List tasks with filtering (completed, priority) and sorting
- Pagination support

### Non-Functional Requirements
- RESTful JSON API with standard HTTP status codes
- Input validation with meaningful error messages
- Consistent error response format

### Out of Scope
- Frontend/UI
- Real-time updates (WebSocket)
- User management/authentication
- Task execution

## Technical Specification

### Tech Stack
| Layer | Technology | Rationale |
|-------|------------|-----------|
| Runtime | Node.js 20 LTS | Stable, async I/O |
| Framework | Express.js 4.x | Minimal, mature |
| Language | TypeScript 5.x | Type safety |
| Database | SQLite (better-sqlite3) | Zero config, portable |
| Validation | Zod | TypeScript-first |
| Testing | Vitest + Supertest | Fast, TS-native |

### Task Entity
```typescript
{
  id: string (UUID),
  title: string (1-255 chars),
  description: string | null (max 2000),
  completed: boolean (default: false),
  priority: 'low' | 'medium' | 'high' (default: 'medium'),
  dueDate: string (ISO datetime) | null,
  createdAt: string (ISO datetime),
  updatedAt: string (ISO datetime)
}
```

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/tasks | List tasks (with filters) |
| GET | /api/v1/tasks/:id | Get single task |
| POST | /api/v1/tasks | Create task |
| PUT | /api/v1/tasks/:id | Full update |
| PATCH | /api/v1/tasks/:id | Partial update |
| DELETE | /api/v1/tasks/:id | Delete task |

### File Structure
```
task-api/
├── src/
│   ├── index.ts
│   ├── app.ts
│   ├── config/
│   ├── controllers/
│   ├── middleware/
│   ├── repositories/
│   ├── routes/
│   ├── schemas/
│   ├── services/
│   ├── db/
│   └── types/
├── tests/
├── package.json
├── tsconfig.json
└── README.md
```

### Error Response Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": [{ "field": "name", "message": "..." }]
  }
}
```
