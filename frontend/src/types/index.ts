export type EventCategory =
  | "세미나"
  | "워크샵"
  | "컨퍼런스"
  | "정기회의"
  | "네트워킹"
  | "축제"
  | "대회"
  | "기타";

export type EventStatus = "기획중" | "확정" | "진행중" | "완료" | "취소";

export type TaskStatus = "할일" | "진행중" | "완료" | "보류";

export interface Event {
  id: string;
  title: string;
  category: EventCategory;
  status: EventStatus;
  startDate: Date;
  endDate: Date;
  location: string;
  isOnline: boolean;
  expectedAttendees: number;
  actualAttendees: number;
  budget: number;
  actualCost: number;
  manager: string;
  tags: string[];
}

export interface Task {
  id: string;
  eventId: string;
  title: string;
  status: TaskStatus;
  assignee: string;
  dueDate: Date;
  priority: 1 | 2 | 3;
}

export interface BudgetItem {
  id: string;
  eventId: string;
  category: string;
  description: string;
  plannedAmount: number;
  actualAmount: number;
  isPaid: boolean;
}

export interface Reminder {
  eventId: string;
  eventTitle: string;
  daysUntil: number;
  message: string;
  priority: "high" | "medium" | "low";
}

export interface Stats {
  totalEvents: number;
  totalAttendees: number;
  totalBudget: number;
  totalActualCost: number;
  averageAttendanceRate: number;
  budgetEfficiency: number;
  costPerAttendee: number;
  taskCompletionRate: number;
  averageFeedbackScore: number;
}

export interface CategoryData {
  name: string;
  value: number;
}

export interface MonthlyData {
  month: string;
  count: number;
}
