import { taskRepository } from '../repositories/task.repository';
import { NotFoundError } from '../middleware/errors';
import {
  Task,
  CreateTaskDto,
  UpdateTaskDto,
  PatchTaskDto,
  TaskQuery,
} from '../schemas/task.schema';

export class TaskService {
  async getAllTasks(filters?: TaskQuery): Promise<Task[]> {
    const repoFilters = filters
      ? {
          completed: filters.completed === 'true' ? true : filters.completed === 'false' ? false : undefined,
          priority: filters.priority,
          sort: filters.sort,
          order: filters.order,
        }
      : undefined;
    return await taskRepository.findAll(repoFilters);
  }

  async getTaskById(id: string): Promise<Task> {
    const task = await taskRepository.findById(id);
    if (!task) {
      throw new NotFoundError('Task', id);
    }
    return task;
  }

  async createTask(data: CreateTaskDto): Promise<Task> {
    return await taskRepository.create(data);
  }

  async updateTask(id: string, data: UpdateTaskDto): Promise<Task> {
    const result = await taskRepository.update(id, data);
    if (!result) {
      throw new NotFoundError('Task', id);
    }
    return result;
  }

  async patchTask(id: string, data: PatchTaskDto): Promise<Task> {
    const result = await taskRepository.patch(id, data);
    if (!result) {
      throw new NotFoundError('Task', id);
    }
    return result;
  }

  async deleteTask(id: string): Promise<void> {
    const deleted = await taskRepository.delete(id);
    if (!deleted) {
      throw new NotFoundError('Task', id);
    }
  }
}

export const taskService = new TaskService();
