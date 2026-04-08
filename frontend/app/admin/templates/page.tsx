'use client';

import { useState, useEffect } from 'react';
import Image from 'next/image';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Template {
  id: number;
  name: string;
  image_path: string;
  category: string;
  is_builtin: number;
  created_at: string;
}

export default function AdminTemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  useEffect(() => {
    fetchTemplates();
  }, []);
  
  const fetchTemplates = async () => {
    try {
      const res = await fetch(`${API_URL}/api/templates`);
      if (res.ok) {
        const data = await res.json();
        setTemplates(data);
      }
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  };
  
  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setUploading(true);
    setError(null);
    setSuccess(null);
    
    const formData = new FormData(e.currentTarget);
    
    try {
      const res = await fetch(`${API_URL}/api/templates`, {
        method: 'POST',
        credentials: 'include',
        body: formData,
      });
      
      if (res.ok) {
        const newTemplate = await res.json();
        setTemplates([...templates, newTemplate]);
        setSuccess('Template uploaded successfully!');
        e.currentTarget.reset();
      } else {
        const errorData = await res.json();
        setError(errorData.detail || 'Failed to upload template');
      }
    } catch {
      setError('Network error: Failed to upload template');
    } finally {
      setUploading(false);
    }
  };
  
  const handleDelete = async (id: number) => {
    if (!confirm('Delete this template? This action cannot be undone.')) return;
    
    try {
      const res = await fetch(`${API_URL}/api/templates/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      
      if (res.ok) {
        setTemplates(templates.filter(t => t.id !== id));
        setSuccess('Template deleted successfully!');
      } else {
        const errorData = await res.json();
        setError(errorData.detail || 'Failed to delete template');
      }
    } catch {
      setError('Network error: Failed to delete template');
    }
  };
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Manage Templates (Admin)</h1>
      
      {error && (
        <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}
      
      {success && (
        <div className="mb-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
          {success}
        </div>
      )}
      
      <form onSubmit={handleUpload} className="mb-8 border rounded-lg p-6 bg-white shadow">
        <h2 className="text-xl font-medium mb-4">Upload New Template</h2>
        
        <div className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm font-medium mb-1">
              Template Name
            </label>
            <input
              type="text"
              id="name"
              name="name"
              required
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="e.g., Classic T-Shirt"
            />
          </div>
          
          <div>
            <label htmlFor="category" className="block text-sm font-medium mb-1">
              Category
            </label>
            <select 
              id="category"
              name="category" 
              required 
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a category</option>
              <option value="t-shirt">T-Shirt</option>
              <option value="hoodie">Hoodie</option>
              <option value="tank">Tank Top</option>
              <option value="long-sleeve">Long Sleeve</option>
              <option value="polo">Polo</option>
            </select>
          </div>
          
          <div>
            <label htmlFor="file" className="block text-sm font-medium mb-1">
              Template Image
            </label>
            <input
              type="file"
              id="file"
              name="file"
              accept="image/*"
              required
              className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="mt-1 text-xs text-gray-500">
              Recommended: PNG or JPG, transparent background, front view only
            </p>
          </div>
          
          <button
            type="submit"
            disabled={uploading}
            className="w-full bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {uploading ? 'Uploading...' : 'Upload Template'}
          </button>
        </div>
      </form>
      
      <div className="border-t pt-6">
        <h2 className="text-xl font-medium mb-4">Existing Templates</h2>
        
        {templates.length === 0 ? (
          <p className="text-gray-600">No templates available yet.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {templates.map((template) => (
              <div key={template.id} className="border rounded-lg p-4 bg-white shadow">
                <div className="relative w-full h-48 bg-gray-50 rounded mb-3">
                  <Image 
                    src={`${API_URL}${template.image_path}`} 
                    alt={template.name}
                    fill
                    className="object-contain"
                    sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                  />
                </div>
                <h3 className="font-medium text-lg">{template.name}</h3>
                <p className="text-sm text-gray-600 capitalize mb-2">{template.category}</p>
                
                {template.is_builtin === 1 ? (
                  <div className="px-3 py-1 bg-gray-100 text-gray-600 text-sm rounded text-center">
                    Built-in (Cannot Delete)
                  </div>
                ) : (
                  <button
                    onClick={() => handleDelete(template.id)}
                    className="w-full bg-red-600 text-white py-2 rounded-lg hover:bg-red-700 transition-colors"
                  >
                    Delete
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
