export interface ChatActionPayload {
  type:
    | 'wallet_topup'
    | 'instructor_card'
    | 'sessions_list'
    | 'faq_info'
    | 'skill_created'
    | 'learning_skill_created'
    | string
  data: Record<string, any>
}

export interface ChatMessageResponse {
  reply: string
  action?: ChatActionPayload | null
  suggested_prompts: string[]
}

export interface ChatHistoryItem {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  action?: ChatActionPayload | null
}
