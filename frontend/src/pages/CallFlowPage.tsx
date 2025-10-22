import React, { useState } from 'react';
import { useQuery } from 'react-query';
import toast from 'react-hot-toast';
import { DocumentArrowDownIcon, SparklesIcon } from '@heroicons/react/24/outline';
import { apiClient } from '../utils/api';

interface Lead {
  id: number;
  name: string;
  partner_name: string;
  email_from: string;
  stage_name: string;
  salesperson_name: string;
  description?: string;
  function?: string;
}

export default function CallFlowPage() {
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Fetch enriched leads
  const { data: leadsData, isLoading } = useQuery(
    'enriched-leads',
    async () => {
      const response = await apiClient.get('/enriched-leads');
      return response.data;
    },
    {
      refetchOnMount: true,
    }
  );

  const handleGenerateCallFlow = async () => {
    if (!selectedLead) {
      toast.error('Please select a lead first');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await apiClient.post(
        '/call-flow/generate',
        { lead_id: selectedLead.id },
        { responseType: 'blob' }
      );

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Discovery_Call_Flow_${selectedLead.name.replace(/\s+/g, '_')}.docx`);
      document.body.appendChild(link);
      link.click();
      link.remove();

      toast.success('Call flow document generated successfully!');
    } catch (error: any) {
      console.error('Error generating call flow:', error);
      toast.error(error.response?.data?.detail || 'Failed to generate call flow document');
    } finally {
      setIsGenerating(false);
    }
  };

  const leads = leadsData?.leads || [];

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Pre-discovery Call Flow Generation</h1>
        <p className="mt-2 text-sm text-gray-600">
          Generate personalized discovery call flow documents based on enriched lead data
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Lead Selection */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Select Lead</h2>

          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-500 border-t-transparent"></div>
            </div>
          ) : leads.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
              <p className="text-sm text-gray-500">No enriched leads found</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {leads.map((lead: Lead) => (
                <button
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  className={`w-full rounded-lg border p-4 text-left transition-all ${
                    selectedLead?.id === lead.id
                      ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-500'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium text-gray-900">{lead.name}</div>
                  <div className="mt-1 text-sm text-gray-500">{lead.partner_name}</div>
                  {lead.function && (
                    <div className="mt-1 text-xs text-gray-400">{lead.function}</div>
                  )}
                  <div className="mt-2 inline-flex items-center rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">
                    {lead.stage_name}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Selected Lead Details & Actions */}
        <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Lead Details</h2>

          {selectedLead ? (
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">Contact Name</label>
                <p className="mt-1 text-gray-900">{selectedLead.name}</p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700">Company</label>
                <p className="mt-1 text-gray-900">{selectedLead.partner_name}</p>
              </div>

              {selectedLead.email_from && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Email</label>
                  <p className="mt-1 text-gray-900">{selectedLead.email_from}</p>
                </div>
              )}

              {selectedLead.function && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Job Title</label>
                  <p className="mt-1 text-gray-900">{selectedLead.function}</p>
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-gray-700">Stage</label>
                <p className="mt-1 text-gray-900">{selectedLead.stage_name}</p>
              </div>

              {selectedLead.description && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Notes</label>
                  <div
                    className="mt-1 text-sm text-gray-600 line-clamp-3 prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: selectedLead.description }}
                  />
                </div>
              )}

              <div className="pt-4 border-t">
                <button
                  onClick={handleGenerateCallFlow}
                  disabled={isGenerating}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {isGenerating ? (
                    <>
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                      Generating Call Flow...
                    </>
                  ) : (
                    <>
                      <SparklesIcon className="h-5 w-5" />
                      Generate Discovery Call Flow
                      <DocumentArrowDownIcon className="h-5 w-5" />
                    </>
                  )}
                </button>

                <p className="mt-3 text-xs text-gray-500 text-center">
                  This will generate a personalized discovery call flow document based on {selectedLead.name}'s enriched data
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center py-16 text-gray-400">
              <p>Select a lead to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
