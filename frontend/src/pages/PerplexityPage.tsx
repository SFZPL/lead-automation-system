import React, { useEffect, useMemo, useState } from 'react';
import toast from 'react-hot-toast';
import {
  ClipboardIcon,
  CheckIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  SparklesIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';

const API_BASE_URL = process.env.REACT_APP_API_BASE || 'http://localhost:8000';

interface LeadPreview {
  id: number;
  name: string;
  email: string;
  company: string;
}

interface PromptData {
  prompt: string;
  leadCount: number;
  leads: LeadPreview[];
}

interface ParsedLead {
  id: number;
  name: string;
  linkedin_url?: string;
  job_title?: string;
  company?: string;
  company_linkedin?: string;
  industry?: string;
  company_size?: string;
  revenue_estimate?: string;
  founded?: string;
  location?: string;
  phone?: string;
  quality_rating?: number;
  confidence?: string;
}

interface ParseResponse {
  parsed_count: number;
  updated: number;
  failed: number;
  errors: string[];
}

const parsePerplexityResults = (text: string): ParsedLead[] => {
  if (!text.trim()) {
    return [];
  }

  const leads: ParsedLead[] = [];
  const leadSections = text.split(/\*\*LEAD \d+:/);

  leadSections.slice(1).forEach((section, index) => {
    const nameMatch = section.match(/^([^*]+)\**/);
    const name = nameMatch ? nameMatch[1].trim() : `Lead ${index + 1}`;

    const extractField = (field: string) => {
      const regex = new RegExp(`${field}:\s*(.+?)(?:\n|$)`, 'i');
      const match = section.match(regex);
      return match ? match[1].trim() : '';
    };

    const qualityMatch = section.match(/Quality Rating:\s*(\d+)/i);
    const quality = qualityMatch ? parseInt(qualityMatch[1], 10) : 0;

    leads.push({
      id: index + 1,
      name,
      linkedin_url: extractField('LinkedIn URL'),
      job_title: extractField('Job Title'),
      company: extractField('Company'),
      company_linkedin: extractField('Company LinkedIn'),
      industry: extractField('Industry'),
      company_size: extractField('Company Size'),
      revenue_estimate: extractField('Revenue Estimate'),
      founded: extractField('Founded'),
      location: extractField('Location'),
      phone: extractField('Phone'),
      quality_rating: quality,
      confidence: extractField('Confidence'),
    });
  });

  return leads;
};

const PerplexityPage: React.FC = () => {
  const [promptData, setPromptData] = useState<PromptData | null>(null);
  const [isFetchingPrompt, setIsFetchingPrompt] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [perplexityResults, setPerplexityResults] = useState('');
  const [parsedLeads, setParsedLeads] = useState<ParsedLead[]>([]);
  const [isUpdating, setIsUpdating] = useState(false);
  const [parseSummary, setParseSummary] = useState<ParseResponse | null>(null);

  const fetchPrompt = async () => {
    setIsFetchingPrompt(true);
    setParseSummary(null);
    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/generate`, {
      method: 'POST',
    });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }
      const data = await response.json();
      const leads = (data.leads || []).map((lead: any, index: number): LeadPreview => ({
        id: lead.id ?? index,
        name: lead.full_name ?? lead.name ?? 'Unknown',
        email: lead.email ?? '',
        company: lead.company_name ?? lead.company ?? '',
      }));

      setPromptData({
        prompt: data.prompt,
        leadCount: data.lead_count ?? leads.length,
        leads,
      });

      if (leads.length === 0) {
        toast('No unenriched leads found in Odoo.', { icon: 'ℹ️' });
      } else {
        toast.success(`Fetched ${leads.length} lead${leads.length === 1 ? '' : 's'}`);
      }
    } catch (error: any) {
      console.error('Failed to fetch prompt:', error);
      toast.error(`Unable to fetch leads: ${error.message || error}`);
    } finally {
      setIsFetchingPrompt(false);
    }
  };

  const copyPrompt = async () => {
    if (!promptData) {
      return;
    }
    try {
      await navigator.clipboard.writeText(promptData.prompt);
      setIsCopied(true);
      toast.success('Prompt copied to clipboard');
      setTimeout(() => setIsCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy prompt');
    }
  };

  useEffect(() => {
    setParsedLeads(parsePerplexityResults(perplexityResults));
  }, [perplexityResults]);

  const handleProcessResults = async () => {
    if (!perplexityResults.trim()) {
      toast.error('Paste the Perplexity response before updating Odoo');
      return;
    }

    setIsUpdating(true);
    setParseSummary(null);
    toast.loading('Updating leads in Odoo...');

    try {
      const response = await fetch(`${API_BASE_URL}/perplexity/parse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          results_text: perplexityResults,
          update: true,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `Request failed with status ${response.status}`);
      }

      const data: ParseResponse = await response.json();
      setParseSummary(data);
      toast.dismiss();
      toast.success(`Updated ${data.updated} lead${data.updated === 1 ? '' : 's'} in Odoo`);
      setPerplexityResults('');
      setParsedLeads([]);
    } catch (error: any) {
      console.error('Failed to update leads:', error);
      toast.dismiss();
      toast.error(`Failed to update leads: ${error.message || error}`);
    } finally {
      setIsUpdating(false);
    }
  };

  const parsedLeadSummary = useMemo(
    () => parsedLeads.map((lead) => `${lead.name}${lead.job_title ? ` — ${lead.job_title}` : ''}`),
    [parsedLeads]
  );

  return (
    <div className="max-w-6xl mx-auto">
      <div className="mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">Lead Enrichment Workflow</h1>
        <p className="mt-4 text-lg text-gray-600">
          Fetch raw leads, generate a Perplexity prompt, paste the AI response, and push the enriched data back into Odoo.
        </p>
      </div>

      <div className="space-y-12">
        <section className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="md:col-span-1">
            <h2 className="text-lg font-semibold text-gray-900">
              <span className="text-blue-600">Step 1:</span> Fetch Leads
            </h2>
            <p className="mt-1 text-sm text-gray-600">Retrieve unenriched leads from Odoo.</p>
          </div>
          <div className="md:col-span-2">
            <div className="rounded-lg border border-gray-200 bg-white/5">
              {promptData ? (
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <p className="text-sm text-gray-500">Fetched Leads</p>
                      <p className="text-2xl font-semibold text-gray-900">{promptData.leadCount}</p>
                    </div>
                    <button
                      onClick={fetchPrompt}
                      disabled={isFetchingPrompt}
                      className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
                    >
                      <UserGroupIcon className="h-4 w-4" />
                      {isFetchingPrompt ? 'Refreshing...' : 'Refresh Leads'}
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="border-b border-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left font-medium text-gray-900">Name</th>
                          <th className="px-4 py-2 text-left font-medium text-gray-900">Email</th>
                          <th className="px-4 py-2 text-left font-medium text-gray-900">Company</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {promptData.leads.map((lead) => (
                          <tr key={lead.id}>
                            <td className="px-4 py-2 whitespace-nowrap text-gray-900">{lead.name}</td>
                            <td className="px-4 py-2 whitespace-nowrap text-gray-600">{lead.email || '—'}</td>
                            <td className="px-4 py-2 whitespace-nowrap text-gray-600">{lead.company || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center">
                  <UserGroupIcon className="mx-auto h-12 w-12 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-500">No leads fetched yet</p>
                  <button
                    onClick={fetchPrompt}
                    disabled={isFetchingPrompt}
                    className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
                  >
                    <UserGroupIcon className="h-4 w-4" />
                    {isFetchingPrompt ? 'Fetching...' : 'Fetch Leads'}
                  </button>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="md:col-span-1">
            <h2 className="text-lg font-semibold text-gray-900">
              <span className="text-blue-600">Step 2:</span> Generate Prompt
            </h2>
            <p className="mt-1 text-sm text-gray-600">Copy the generated prompt into Perplexity.</p>
          </div>
          <div className="md:col-span-2 space-y-4">
            <button
              onClick={fetchPrompt}
              disabled={isFetchingPrompt}
              className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50"
            >
              <SparklesIcon className="h-5 w-5" />
              {isFetchingPrompt ? 'Generating...' : 'Generate AI Prompt'}
            </button>

            {promptData ? (
              <div className="relative">
                <textarea
                  className="w-full rounded-lg border border-gray-200 bg-white/5 p-4 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:ring-blue-600"
                  value={promptData.prompt}
                  readOnly
                  rows={6}
                />
                <button
                  onClick={copyPrompt}
                  className="absolute top-2 right-2 flex items-center gap-1 rounded bg-blue-600/10 px-2 py-1 text-xs text-blue-600 hover:bg-blue-600/20"
                >
                  <ClipboardIcon className="h-4 w-4" />
                  {isCopied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-lg border border-dashed border-gray-300 p-4 text-sm text-gray-500">
                <ExclamationTriangleIcon className="h-5 w-5 text-yellow-500" />
                Fetch leads first to generate the prompt.
              </div>
            )}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="md:col-span-1">
            <h2 className="text-lg font-semibold text-gray-900">
              <span className="text-blue-600">Step 3:</span> Paste Results
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              After running the prompt in Perplexity, copy the entire response and paste it here.
            </p>
          </div>
          <div className="md:col-span-2 space-y-4">
            <textarea
              className="w-full rounded-lg border border-gray-200 bg-white/5 p-4 text-sm text-gray-900 placeholder:text-gray-400 focus:border-blue-600 focus:ring-blue-600"
              placeholder="Paste the full Perplexity response..."
              value={perplexityResults}
              onChange={(event) => setPerplexityResults(event.target.value)}
              rows={8}
            />

            {parsedLeads.length > 0 && (
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                <div className="flex items-center gap-2 text-blue-800 font-medium">
                  <DocumentTextIcon className="h-5 w-5" />
                  Previewing {parsedLeads.length} lead{parsedLeads.length === 1 ? '' : 's'}
                </div>
                <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {parsedLeadSummary.map((summary, index) => (
                    <li key={index} className="text-sm text-blue-900">• {summary}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        <section className="grid grid-cols-1 gap-8 md:grid-cols-3">
          <div className="md:col-span-1">
            <h2 className="text-lg font-semibold text-gray-900">
              <span className="text-blue-600">Step 4:</span> Update Odoo
            </h2>
            <p className="mt-1 text-sm text-gray-600">
              Push the enriched data back into Odoo once it looks correct.
            </p>
          </div>
          <div className="md:col-span-2 space-y-4">
            <button
              onClick={handleProcessResults}
              disabled={isUpdating || !parsedLeads.length}
              className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-green-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-green-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-green-600 disabled:opacity-50"
            >
              <CheckIcon className="h-5 w-5" />
              {isUpdating ? 'Updating...' : `Update ${parsedLeads.length} Lead${parsedLeads.length === 1 ? '' : 's'} in Odoo`}
            </button>

            {parseSummary && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-6">
                <div className="flex items-center gap-2 mb-4">
                  <CheckIcon className="h-6 w-6 text-green-600" />
                  <h3 className="text-lg font-semibold text-green-900">Update Complete</h3>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="bg-white p-4 rounded-lg border border-green-200">
                    <div className="text-2xl font-bold text-green-600">{parseSummary.parsed_count}</div>
                    <div className="text-sm text-gray-600">Leads Parsed</div>
                  </div>
                  <div className="bg-white p-4 rounded-lg border border-green-200">
                    <div className="text-2xl font-bold text-green-600">{parseSummary.updated}</div>
                    <div className="text-sm text-gray-600">Updated in Odoo</div>
                  </div>
                  <div className="bg-white p-4 rounded-lg border border-green-200">
                    <div className="text-2xl font-bold text-red-600">{parseSummary.failed}</div>
                    <div className="text-sm text-gray-600">Failed Updates</div>
                  </div>
                </div>

                {parseSummary.errors && parseSummary.errors.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-medium text-red-900 mb-2">Errors</h4>
                    <div className="space-y-2">
                      {parseSummary.errors.map((error, index) => (
                        <div key={index} className="text-sm text-red-600 bg-red-50 p-2 rounded border border-red-200">
                          {error}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default PerplexityPage;
