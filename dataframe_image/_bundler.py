from pathlib import Path
import json
import base64

from tornado import gen


def _jupyter_bundlerextension_paths():
    return [{
        "name": "dataframe_image_bundler",
        "module_name": "dataframe_image._bundler",
        "label" : "DataFrame as Image",
        "group" : "download",
    }]


def convert(model, handler):
    from ._convert import Converter

    arguments = ['to', 'use', 'centerdf', 'latex_command', 'max_rows', 'max_cols', 
                 'ss_width', 'ss_height', 'resize', 'chrome_path', 'limit', 
                 'document_name', 'execute', 'save_notebook']

    kwargs = {arg: handler.get_query_argument(arg, None) for arg in arguments}
    path = model['path']
    kwargs['filename'] = path
    kwargs['to'] = kwargs['to']
    if kwargs['to'] == 'both':
        kwargs['to'] = ['md', 'pdf']
    kwargs['use'] == kwargs['use'] or None
    kwargs['centerdf'] = kwargs['centerdf'] == "True"
    kwargs['latex_command'] = [tag.strip() for tag in kwargs['latex_command'].split()]
    kwargs['max_rows'] = 30 if kwargs['max_rows'] == '' else int(kwargs['max_rows'])
    kwargs['max_cols'] = 10 if kwargs['max_cols'] == '' else int(kwargs['max_cols'])
    kwargs['ss_width'] = 1000 if kwargs['ss_width'] == '' else int(kwargs['ss_width'])
    kwargs['ss_height'] = 900 if kwargs['ss_height'] == '' else int(kwargs['ss_height'])
    kwargs['resize'] = 1 if kwargs['resize'] == '' else float(kwargs['resize'])
    kwargs['chrome_path'] = kwargs['chrome_path'] or None
    kwargs['limit'] = None if kwargs['limit'] == '' else int(kwargs['limit'])
    kwargs['document_name'] = kwargs['document_name'] or None
    kwargs['execute'] = kwargs['execute'] == "True"
    kwargs['save_notebook'] = kwargs['save_notebook'] == "True"
    kwargs['output_dir'] = None
    kwargs['image_dir_name'] = None
    kwargs['web_app'] = True
   
    try:
        converter = Converter(**kwargs)
        converter.convert()
    except Exception as e:
        import traceback
        error_name = type(e).__name__
        error = f'{error_name}: {str(e)}'
        tb = traceback.format_exc()
        msg = error + f'\n\n{tb}'

        converter.success = False
        converter.error_msg = msg
    else:
        if 'pdf_data' in converter.return_data or 'md_data' in converter.return_data:
            converter.success = True
        else:
            converter.success = False
            converter.error_msg = 'Error: \n' + str(converter.return_data)

    return converter


def read_static_file(name):
    mod_path = Path(__file__).parent
    html_path = mod_path / 'static' / name
    return open(html_path).read()


def get_js(converter):
    fn = converter.document_name
    data = converter.return_data
    
    if converter.to == ['pdf'] and not converter.save_notebook:
        app_type = 'pdf'
        s = base64.b64encode(data['pdf_data']).decode()
    else:
        app_type = 'zip'
        from zipfile import ZipFile, ZIP_DEFLATED
        with ZipFile(f'{fn}.zip', "w", compression=ZIP_DEFLATED) as zf:
            if 'md_data' in data:
                zf.writestr(f'{fn}.md', data['md_data'])
                for image_fn, val in data['md_images'].items():
                    zf.writestr(image_fn, val)
            if 'pdf_data' in data:
                zf.writestr(f'{fn}.pdf', data['pdf_data'])
            if converter.save_notebook:
                zf.writestr(f'{fn}.ipynb', data['notebook'])

        with open(f'{fn}.zip', 'rb') as zf:
            s = base64.b64encode(zf.read()).decode()

    js = read_static_file('download.html').format(s=s, filename=fn, app_type=app_type)
    return js


# synchronous execution
def bundle(handler, model):
    """
    Parameters
    ----------
    handler : tornado.web.RequestHandler
        Handler that serviced the bundle request
    model : dict
        Notebook model from the configured ContentManager
    """
    app_status = handler.get_query_argument('app_status', None)
    
    if app_status is None:
        html = read_static_file('form.html')
        handler.write(html)
    elif app_status == 'waiting':
        converter = convert(model, handler)
        if converter.success: 
            js = get_js(converter)
            handler.write(js)
        else:
            html = read_static_file('fail.html').format(error_msg=converter.error_msg)
            handler.write(html)
    handler.finish()
            