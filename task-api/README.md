# Task API

A RESTful task management API built with Express, TypeScript, and SQLite (using sql.js).

## Description

This API provides a complete CRUD interface for managing tasks with features including:
- Task creation, retrieval, updating, and deletion
- Task filtering by completion status and priority
- Sorting by creation date, due date, or priority
- Input validation using Zod schemas
- Persistent storage using SQLite with sql.js
- Type-safe implementation with TypeScript

## Prerequisites

- Node.js 20 or higher
- npm (comes with Node.js)

## Installation

1. Clone the repository and navigate to the project directory:

```bash
cd task-api
```

2. Install dependencies:

```bash
npm install
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Configure the environment variables in `.env`:

```env
# Application
NODE_ENV=development
PORT=3000

# Database
DATABASE_PATH=./data/tasks.db

# CORS (optional - comma separated origins)
# CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

## Running the Application

### Development Mode (with auto-reload)

```bash
npm run dev
```

The API will be available at `http://localhost:3000`.

### Production Mode

1. Build the project:

```bash
npm run build
```

2. Start the server:

```bash
npm start
```

## API Endpoints

### Health Check

**GET** `/health`

Check if the API is running.

**Response:**
```json
{
  "status": "ok"
}
```

### Get All Tasks

**GET** `/api/v1/tasks`

Retrieve all tasks with optional filtering and sorting.

**Query Parameters:**
- `completed` (optional): Filter by completion status (`true` or `false`)
- `priority` (optional): Filter by priority (`low`, `medium`, or `high`)
- `sort` (optional): Sort field (`createdAt`, `dueDate`, or `priority`)
- `order` (optional): Sort order (`asc` or `desc`, default: `desc`)

**Example:**
```bash
curl http://localhost:3000/api/v1/tasks?completed=false&priority=high&sort=dueDate&order=asc
```

**Response:**
```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "title": "Complete project",
    "description": "Finish the task API implementation",
    "completed": false,
    "priority": "high",
    "dueDate": "2024-12-31T23:59:59.999Z",
    "createdAt": "2024-01-15T10:30:00.000Z",
    "updatedAt": "2024-01-15T10:30:00.000Z"
  }
]
```

### Get Task by ID

**GET** `/api/v1/tasks/:id`

Retrieve a specific task by its ID.

**Example:**
```bash
curl http://localhost:3000/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000
```

**Response:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Complete project",
  "description": "Finish the task API implementation",
  "completed": false,
  "priority": "high",
  "dueDate": "2024-12-31T23:59:59.999Z",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T10:30:00.000Z"
}
```

**Error Response (404):**
```json
{
  "error": "Task not found",
  "code": "TASK_NOT_FOUND"
}
```

### Create Task

**POST** `/api/v1/tasks`

Create a new task.

**Request Body:**
```json
{
  "title": "Complete project",
  "description": "Finish the task API implementation",
  "completed": false,
  "priority": "high",
  "dueDate": "2024-12-31T23:59:59.999Z"
}
```

**Required Fields:**
- `title` (string, 1-255 characters)

**Optional Fields:**
- `description` (string, max 2000 characters, nullable, default: `null`)
- `completed` (boolean, default: `false`)
- `priority` (`low` | `medium` | `high`, default: `medium`)
- `dueDate` (ISO 8601 datetime string, nullable, default: `null`)

**Example:**
```bash
curl -X POST http://localhost:3000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Complete project",
    "description": "Finish the task API implementation",
    "priority": "high",
    "dueDate": "2024-12-31T23:59:59.999Z"
  }'
```

**Response (201):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Complete project",
  "description": "Finish the task API implementation",
  "completed": false,
  "priority": "high",
  "dueDate": "2024-12-31T23:59:59.999Z",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T10:30:00.000Z"
}
```

**Error Response (400):**
```json
{
  "error": "Validation failed",
  "code": "VALIDATION_ERROR",
  "details": [
    {
      "field": "title",
      "message": "String must contain at least 1 character(s)"
    }
  ]
}
```

### Update Task (Full Update)

**PUT** `/api/v1/tasks/:id`

Replace a task with new data. All fields are required.

**Request Body:**
```json
{
  "title": "Updated project",
  "description": "Updated description",
  "completed": true,
  "priority": "medium",
  "dueDate": null
}
```

**Example:**
```bash
curl -X PUT http://localhost:3000/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Updated project",
    "description": "Updated description",
    "completed": true,
    "priority": "medium",
    "dueDate": null
  }'
```

**Response (200):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Updated project",
  "description": "Updated description",
  "completed": true,
  "priority": "medium",
  "dueDate": null,
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T14:20:00.000Z"
}
```

### Update Task (Partial Update)

**PATCH** `/api/v1/tasks/:id`

Update specific fields of a task. Only include the fields you want to change.

**Request Body:**
```json
{
  "completed": true
}
```

**Example:**
```bash
curl -X PATCH http://localhost:3000/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{
    "completed": true
  }'
```

**Response (200):**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Complete project",
  "description": "Finish the task API implementation",
  "completed": true,
  "priority": "high",
  "dueDate": "2024-12-31T23:59:59.999Z",
  "createdAt": "2024-01-15T10:30:00.000Z",
  "updatedAt": "2024-01-15T14:25:00.000Z"
}
```

### Delete Task

**DELETE** `/api/v1/tasks/:id`

Delete a task by its ID.

**Example:**
```bash
curl -X DELETE http://localhost:3000/api/v1/tasks/123e4567-e89b-12d3-a456-426614174000
```

**Response (204):**
No content (empty response body)

**Error Response (404):**
```json
{
  "error": "Task not found",
  "code": "TASK_NOT_FOUND"
}
```

## Testing

Run the test suite:

```bash
npm test
```

Run tests in watch mode:

```bash
npm run test:watch
```

Run tests once (CI mode):

```bash
npm run test:run
```

## Development

### Type Checking

Check TypeScript types without emitting files:

```bash
npm run lint
```

### Project Structure

```
task-api/
├── src/
│   ├── config/          # Configuration and database setup
│   ├── controllers/     # Request handlers
│   ├── middleware/      # Express middleware
│   ├── repositories/    # Data access layer
│   ├── routes/          # API route definitions
│   ├── schemas/         # Zod validation schemas
│   ├── services/        # Business logic
│   ├── app.ts           # Express app setup
│   └── index.ts         # Application entry point
├── tests/
│   └── integration/     # Integration tests
├── data/                # SQLite database storage
├── .env                 # Environment variables
└── package.json         # Project dependencies
```

## Error Handling

The API uses consistent error responses across all endpoints:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": []
}
```

Common error codes:
- `VALIDATION_ERROR` - Invalid request data (400)
- `TASK_NOT_FOUND` - Task does not exist (404)
- `ROUTE_NOT_FOUND` - API endpoint does not exist (404)
- `INTERNAL_SERVER_ERROR` - Unexpected server error (500)

## License

MIT
