import React, { useState } from 'react';
import { XMarkIcon, UserPlusIcon } from '@heroicons/react/24/outline';
import { useMutation, useQueryClient } from 'react-query';
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
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [notes, setNotes] = useState('');
  const queryClient = useQueryClient();

  const assignMutation = useMutation(
    async () => {
      if (!selectedUserId) throw new Error('Please select a user');

      return api.createLeadAssignment({
        conversation_id: lead.conversation_id,
        external_email: lead.external_email,
        subject: lead.subject,
        assigned_to_user_id: selectedUserId,
        lead_data: lead.lead_data,
        notes: notes.trim() || undefined,
      });
    },
    {
      onSuccess: () => {
        toast.success('Lead assigned successfully!');
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
                Assign to
              </label>
              <select
                id="assignee"
                value={selectedUserId || ''}
                onChange={(e) => setSelectedUserId(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                required
              >
                <option value="">Select a user...</option>
                {users.map((user) => (
                  <option key={user.id} value={user.id}>
                    {user.name} ({user.email})
                  </option>
                ))}
              </select>
            </div>

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
