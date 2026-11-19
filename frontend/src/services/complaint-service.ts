/**
 * Servicio API para radicación de quejas, consulta y arbitraje administrativo
 * (HU-43 / RF-GOV-01, RF-GOV-02, RF-GOV-03).
 */
import { apiClient } from '@/services/api-client'
import type {
  Complaint,
  ComplaintCreatePayload,
  ComplaintResolvePayload,
} from '@/types/complaint'

export async function submitComplaint(payload: ComplaintCreatePayload): Promise<Complaint> {
  const response = await apiClient.post<Complaint>('/complaints', payload, {
    showToastOnError: true,
    showToastOnSuccess: true,
  })
  if (!response.data) {
    throw new Error(response.message || 'Error al radicar la queja.')
  }
  return response.data
}

export async function getMyComplaints(
  page = 1,
  pageSize = 20
): Promise<{ items: Complaint[]; total: number }> {
  const response = await apiClient.get<Complaint[]>(
    `/complaints/my?page=${page}&page_size=${pageSize}`,
    {
      showToastOnError: true,
    }
  )
  return {
    items: response.data || [],
    total: response.count ?? (response.data || []).length,
  }
}

export async function getAdminComplaints(
  statusFilter?: string,
  page = 1,
  pageSize = 20
): Promise<{ items: Complaint[]; total: number }> {
  const statusParam = statusFilter && statusFilter !== 'ALL' ? `&status_filter=${statusFilter}` : ''
  const response = await apiClient.get<Complaint[]>(
    `/admin/complaints?page=${page}&page_size=${pageSize}${statusParam}`,
    {
      showToastOnError: true,
    }
  )
  return {
    items: response.data || [],
    total: response.count ?? (response.data || []).length,
  }
}

export async function getAdminComplaintDetail(complaintId: string): Promise<Complaint> {
  const response = await apiClient.get<Complaint>(`/admin/complaints/${complaintId}`, {
    showToastOnError: true,
  })
  if (!response.data) {
    throw new Error(response.message || 'Queja no encontrada.')
  }
  return response.data
}

export async function resolveComplaint(
  complaintId: string,
  payload: ComplaintResolvePayload
): Promise<Complaint> {
  const response = await apiClient.patch<Complaint>(
    `/admin/complaints/${complaintId}/resolve`,
    payload,
    {
      showToastOnError: true,
      showToastOnSuccess: true,
    }
  )
  if (!response.data) {
    throw new Error(response.message || 'Error al emitir el dictamen arbitral.')
  }
  return response.data
}
