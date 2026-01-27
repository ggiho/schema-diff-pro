# Task Management REST API - Implementation Plan

## Task Entity
```typescript
{
  id: string;           // UUID
  title: string;        // Required, 1-255 chars
  description: string;  // Optional, max 2000 chars
  completed: boolean;   // Default: false
  priority: 'low' | 'medium' | 'high';  // Default: 'medium'
  dueDate: string | null;  // ISO 8601 date, optional
  createdAt: string;    // ISO 8601 timestamp
  updatedAt: string;    // ISO 8601 timestamp
}
```

## API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/tasks | List tasks (with filters) |
| GET | /api/v1/tasks/:id | Get single task |
| POST | /api/v1/tasks | Create task |
| PUT | /api/v1/tasks/:id | Full update |
| PATCH | /api/v1/tasks/:id | Partial update |
| DELETE | /api/v1/tasks/:id | Delete task |

## Implementation Phases

### Phase 1: Project Foundation
- [x] 1.1 Initialize project (package.json, tsconfig.json, .gitignore)
- [x] 1.2 Install dependencies
- [x] 1.3 Configure scripts

### Phase 2: Configuration Layer
- [x] 2.1 Environment configuration (src/config/env.ts)
- [x] 2.2 Database configuration (src/config/database.ts)

### Phase 3: Database Layer
- [x] 3.1 Database schema & migrations
- [x] 3.2 Task repository

### Phase 4: Validation & Error Handling
- [x] 4.1 Zod schemas (src/schemas/task.schema.ts)
- [x] 4.2 Validation middleware
- [x] 4.3 Custom error classes
- [x] 4.4 Global error handler

### Phase 5: Service Layer
- [x] 5.1 Task service (business logic)

### Phase 6: Controller & Routes
- [x] 6.1 Task controller
- [x] 6.2 Task routes

### Phase 7: Application Bootstrap
- [x] 7.1 Express app configuration
- [x] 7.2 Server entry point

### Phase 8: Testing
- [x] 8.1 Test configuration
- [x] 8.2 Integration tests

### Phase 9: Documentation
- [x] 9.1 README documentation

## File Structure
```
task-api/
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── .env.example
├── .gitignore
├── README.md
├── src/
│   ├── index.ts
│   ├── app.ts
│   ├── config/
│   ├── db/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── controllers/
│   ├── routes/
│   └── middleware/
└── tests/
```
