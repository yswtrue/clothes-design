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

async function getTemplates(): Promise<Template[]> {
  try {
    const res = await fetch(`${API_URL}/api/templates`, {
      cache: 'no-store',
    });
    
    if (!res.ok) {
      throw new Error('Failed to fetch templates');
    }
    
    return res.json();
  } catch (error) {
    console.error('Error fetching templates:', error);
    return [];
  }
}

export default async function TemplatesPage() {
  const templates = await getTemplates();
  
  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Garment Templates</h1>
      
      {templates.length === 0 ? (
        <p className="text-gray-600">No templates available yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((template) => (
            <div 
              key={template.id} 
              className="border rounded-lg p-4 hover:shadow-lg transition-shadow"
            >
              <div className="relative w-full h-64 bg-gray-50 rounded mb-3">
                <Image
                  src={`${API_URL}${template.image_path}`}
                  alt={template.name}
                  fill
                  className="object-contain"
                  sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                />
              </div>
              <h3 className="mt-3 font-medium text-lg">{template.name}</h3>
              <p className="text-sm text-gray-600 capitalize">{template.category}</p>
              {template.is_builtin === 1 && (
                <span className="inline-block mt-2 px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                  Built-in
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
