import React, { useState, useEffect } from 'react';
import { XMarkIcon, UserPlusIcon } from '@heroicons/react/24/outline';
import { useMutation, useQuery, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import api from '../utils/api';

interface AssignLeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  lead: {
    conversation_id: string;
    external_email: string;
    subject: string;
    lead_data: any;
  };
  users: Array<{ id: number; name: string; email: string }>;
}

const AssignLeadModal: React.FC<AssignLeadModalProps> = ({ isOpen, onClose, lead, users }) => {
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [sendTeamsNotification, setSendTeamsNotification] = useState<boolean>(true);
  const queryClient = useQueryClient();

  // Fetch Teams members if available
  const teamsQuery = useQuery(
    'teams-members',
    () => api.getTeamsMembers(),
    {
      enabled: isOpen,
      retry: false,
      onError: (error: any) => {
        // Silently fail if Teams not configured or unauthorized
        console.log('Teams members not available:', error);
      }
    }
  );

  const teamsMembers = teamsQuery.data?.data?.members || [];
  const effectiveUsers = teamsMembers.length > 0 ? teamsMembers : users;

  const assignMutation = useMutation(
    async () => {
      if (!selectedUserId) throw new Error('Please select a user');

      // Determine if using Teams member or database user
      const isTeamsMember = teamsMembers.length > 0;
      const selectedMember = isTeamsMember
        ? teamsMembers.find((m: any) => m.id === selectedUserId)
        : null;

      // Create lead assignment
      const assignmentData: any = {
        conversation_id: lead.conversation_id,
        external_email: lead.external_email,
        subject: lead.subject,
        lead_data: lead.lead_data,
        notes: notes.trim() || undefined,
      };

      // Add appropriate user ID based on source
      if (isTeamsMember && selectedMember) {
        assignmentData.assigned_to_teams_id = selectedMember.id;
        assignmentData.assigned_to_name = selectedMember.name;
        assignmentData.assigned_to_email = selectedMember.email;
      } else {
        assignmentData.assigned_to_user_id = parseInt(selectedUserId as string);
      }

      const assignmentResponse = await api.createLeadAssignment(assignmentData);

      // Send Teams notification if enabled and Teams members are available
      if (sendTeamsNotification && teamsMembers.length > 0) {
        const selectedMember = teamsMembers.find((m: any) => m.id === selectedUserId);
        if (selectedMember) {
          try {
            await api.sendTeamsAssignmentNotification({
              assignee_user_id: selectedMember.id,
              assignee_name: selectedMember.name,
              lead_subject: lead.subject,
              lead_email: lead.external_email,
              lead_company: lead.lead_data?.partner_name || lead.lead_data?.company_name,
              notes: notes.trim() || undefined
            });
          } catch (error) {
            console.error('Failed to send Teams notification:', error);
            // Don't fail the whole operation if notification fails
          }
        }
      }

      return assignmentResponse;
    },
    {
      onSuccess: () => {
        const notificationMsg = sendTeamsNotification && teamsMembers.length > 0
          ? 'Lead assigned and Teams notification sent!'
          : 'Lead assigned successfully!';
        toast.success(notificationMsg);
        queryClient.invalidateQueries('sent-assignments');
        handleClose();
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || 'Failed to assign lead');
      },
    }
  );

  const handleClose = () => {
    setSelectedUserId(null);
    setNotes('');
    onClose();
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    assignMutation.mutate();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black bg-opacity-30" onClick={handleClose} />

        {/* Modal */}
        <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <UserPlusIcon className="w-6 h-6 text-blue-600" />
              <h2 className="text-xl font-semibold text-gray-900">Assign Lead</h2>
            </div>
            <button
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {/* Lead Info */}
          <div className="mb-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-sm font-medium text-gray-900 mb-1">{lead.subject}</p>
            <p className="text-xs text-gray-600">{lead.external_email}</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            {/* User Selection */}
            <div className="mb-4">
              <label htmlFor="assignee" className="block text-sm font-medium text-gray-700 mb-2">
                Assign to {teamsQuery.isLoading && <span className="text-xs text-gray-500">(Loading Teams members...)</span>}
              </label>
              <select
                id="assignee"
                value={selectedUserId || ''}
                onChange={(e) => setSelectedUserId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
                disabled={teamsQuery.isLoading}
              >
                <option value="">
                  {teamsQuery.isLoading ? 'Loading...' : 'Select a user...'}
                </option>
                {effectiveUsers.map((user: any) => (
                  <option key={user.id} value={user.id}>
                    {user.name} {user.email && `(${user.email})`}
                  </option>
                ))}
              </select>
              {teamsMembers.length > 0 && (
                <p className="mt-1 text-xs text-green-600">✓ Using Teams member list</p>
              )}
            </div>

            {/* Teams Notification Checkbox */}
            {teamsMembers.length > 0 && (
              <div className="mb-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={sendTeamsNotification}
                    onChange={(e) => setSendTeamsNotification(e.target.checked)}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <span className="text-sm text-gray-700">Send Teams notification</span>
                </label>
              </div>
            )}

            {/* Notes */}
            <div className="mb-6">
              <label htmlFor="notes" className="block text-sm font-medium text-gray-700 mb-2">
                Notes (optional)
              </label>
              <textarea
                id="notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                placeholder="Add any context or instructions..."
              />
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleClose}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                disabled={assignMutation.isLoading}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={assignMutation.isLoading || !selectedUserId}
              >
                {assignMutation.isLoading ? 'Assigning...' : 'Assign Lead'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AssignLeadModal;
