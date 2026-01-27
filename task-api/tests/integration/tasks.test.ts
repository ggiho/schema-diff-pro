import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import request from 'supertest';
import { createApp } from '../../src/app.js';
import { getDatabaseManager, closeDatabaseManager } from '../../src/config/database.js';

describe('Task API Integration Tests', () => {
  const app = createApp();
  let baseURL: string;

  beforeAll(async () => {
    // Initialize database
    await getDatabaseManager();
    baseURL = '/api/v1/tasks';
  });

  afterAll(async () => {
    // Close database connection
    await closeDatabaseManager();
  });

  beforeEach(async () => {
    // Clear all tasks before each test
    const dbManager = await getDatabaseManager();
    const db = dbManager.getDb();
    db.run('DELETE FROM tasks');
  });

  describe('GET /api/v1/tasks', () => {
    it('should return empty array initially', async () => {
      const response = await request(app).get(baseURL);

      expect(response.status).toBe(200);
      expect(response.body.data).toEqual([]);
      expect(response.body.meta.total).toBe(0);
    });

    it('should return all tasks', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Test Task',
          description: 'Test Description',
          completed: false,
          priority: 'medium',
        });

      const response = await request(app).get(baseURL);

      expect(response.status).toBe(200);
      expect(response.body.data).toHaveLength(1);
      expect(response.body.data[0].title).toBe('Test Task');
    });
  });

  describe('POST /api/v1/tasks', () => {
    it('should create a task and return 201', async () => {
      const taskData = {
        title: 'New Task',
        description: 'Task Description',
        completed: false,
        priority: 'high',
      };

      const response = await request(app).post(baseURL).send(taskData);

      expect(response.status).toBe(201);
      expect(response.body.data).toMatchObject({
        title: taskData.title,
        description: taskData.description,
        completed: taskData.completed,
        priority: taskData.priority,
      });
      expect(response.body.data.id).toBeDefined();
      expect(response.body.data.createdAt).toBeDefined();
      expect(response.body.data.updatedAt).toBeDefined();
    });

    it('should create task with defaults for optional fields', async () => {
      const taskData = {
        title: 'Minimal Task',
      };

      const response = await request(app).post(baseURL).send(taskData);

      expect(response.status).toBe(201);
      expect(response.body.data.title).toBe(taskData.title);
      expect(response.body.data.completed).toBe(false);
      expect(response.body.data.priority).toBe('medium');
      expect(response.body.data.description).toBeNull();
    });

    it('should return 400 with invalid body', async () => {
      const invalidData = {
        // Missing required title field
        description: 'No title',
      };

      const response = await request(app).post(baseURL).send(invalidData);

      expect(response.status).toBe(400);
      expect(response.body.error).toBeDefined();
    });

    it('should return 400 with invalid priority', async () => {
      const invalidData = {
        title: 'Task',
        priority: 'invalid-priority',
      };

      const response = await request(app).post(baseURL).send(invalidData);

      expect(response.status).toBe(400);
      expect(response.body.error).toBeDefined();
    });
  });

  describe('GET /api/v1/tasks/:id', () => {
    it('should return task by id', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Find Me',
          description: 'Task to find',
        });

      const taskId = createResponse.body.data.id;
      const response = await request(app).get(`${baseURL}/${taskId}`);

      expect(response.status).toBe(200);
      expect(response.body.data.id).toBe(taskId);
      expect(response.body.data.title).toBe('Find Me');
    });

    it('should return 404 with invalid id', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const response = await request(app).get(`${baseURL}/${fakeId}`);

      expect(response.status).toBe(404);
      expect(response.body.error).toBeDefined();
    });
  });

  describe('PUT /api/v1/tasks/:id', () => {
    it('should update task completely', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Original Title',
          description: 'Original Description',
          completed: false,
          priority: 'low',
        });

      const taskId = createResponse.body.data.id;
      const updateData = {
        title: 'Updated Title',
        description: 'Updated Description',
        completed: true,
        priority: 'high',
        dueDate: null,
      };

      const response = await request(app)
        .put(`${baseURL}/${taskId}`)
        .send(updateData);

      expect(response.status).toBe(200);
      expect(response.body.data.title).toBe(updateData.title);
      expect(response.body.data.description).toBe(updateData.description);
      expect(response.body.data.completed).toBe(updateData.completed);
      expect(response.body.data.priority).toBe(updateData.priority);
    });

    it('should return 404 for non-existent task', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const updateData = {
        title: 'Updated Title',
        description: 'Updated Description',
        completed: true,
        priority: 'high',
        dueDate: null,
      };

      const response = await request(app)
        .put(`${baseURL}/${fakeId}`)
        .send(updateData);

      expect(response.status).toBe(404);
    });
  });

  describe('PATCH /api/v1/tasks/:id', () => {
    it('should patch task partially', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Original Title',
          description: 'Original Description',
          completed: false,
          priority: 'medium',
        });

      const taskId = createResponse.body.data.id;
      const patchData = {
        completed: true,
      };

      const response = await request(app)
        .patch(`${baseURL}/${taskId}`)
        .send(patchData);

      expect(response.status).toBe(200);
      expect(response.body.data.completed).toBe(true);
      expect(response.body.data.title).toBe('Original Title'); // Should remain unchanged
      expect(response.body.data.description).toBe('Original Description'); // Should remain unchanged
    });

    it('should return 404 for non-existent task', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const patchData = {
        completed: true,
      };

      const response = await request(app)
        .patch(`${baseURL}/${fakeId}`)
        .send(patchData);

      expect(response.status).toBe(404);
    });
  });

  describe('DELETE /api/v1/tasks/:id', () => {
    it('should delete task and return 204', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Task to Delete',
        });

      const taskId = createResponse.body.data.id;
      const response = await request(app).delete(`${baseURL}/${taskId}`);

      expect(response.status).toBe(204);
      expect(response.body).toEqual({});

      // Verify task is deleted
      const getResponse = await request(app).get(`${baseURL}/${taskId}`);
      expect(getResponse.status).toBe(404);
    });

    it('should return 404 when deleting non-existent task', async () => {
      const fakeId = '00000000-0000-0000-0000-000000000000';
      const response = await request(app).delete(`${baseURL}/${fakeId}`);

      expect(response.status).toBe(404);
    });

    it('should return 404 when deleting same task twice', async () => {
      // Create a task first
      const createResponse = await request(app)
        .post(baseURL)
        .send({
          title: 'Task to Delete Twice',
        });

      const taskId = createResponse.body.data.id;

      // First deletion should succeed
      const firstDelete = await request(app).delete(`${baseURL}/${taskId}`);
      expect(firstDelete.status).toBe(204);

      // Second deletion should return 404
      const secondDelete = await request(app).delete(`${baseURL}/${taskId}`);
      expect(secondDelete.status).toBe(404);
    });
  });
});
