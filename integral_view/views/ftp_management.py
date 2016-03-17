import django, django.template,os

import subprocess, re, shutil

from integralstor_common import audit, zfs,common, certificates, vsftp
from integralstor_unicell import local_users
from integral_view.forms import ftp_management_forms

def view_ftp_configuration(request):
  return_dict = {}
  try:
    if "action" in request.GET:
      if request.GET["action"] == "dirs_created":
        conf = "FTP user home directories successfully created"
      elif request.GET["action"] == "saved":
        conf = "FTP configuration successfully updated"
      if conf:
        return_dict["conf"] = conf

    config, err = vsftp.get_ftp_config()
    if err:
      raise Exception(err)

    return_dict['config'] = config
    return django.shortcuts.render_to_response('view_ftp_configuration.html', return_dict, context_instance = django.template.context.RequestContext(request))

  except Exception, e:
    return_dict['base_template'] = "services_base.html"
    return_dict["page_title"] = 'View FTP service configuration'
    return_dict['tab'] = 'ftp_service_settings'
    return_dict["error"] = 'Error retrieving the FTP service configuration'
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))

def configure_ftp(request):
  return_dict = {}
  try:
    config, err = vsftp.get_ftp_config()
    if err:
      raise Exception(err)
    pools, err = zfs.get_pools()
    ds_list = []
    for pool in pools:
      for ds in pool["datasets"]:
        if ds['properties']['type']['value'] == 'filesystem':
          ds_list.append(ds["name"])
    cert_list, err = certificates.get_certificates()
    if err:
      raise Exception(err)
    cert_name_list = []
    for cert in cert_list:
      cert_name_list.append(cert['name'])
    #print ds_list
    if not ds_list:
      raise Exception('No ZFS datasets available. Please create a dataset before configuring the FTP service.')

    if request.method == 'GET':
      initial = {}
      if config:
        for key in config.keys():
          initial[key] = config[key]
      form = ftp_management_forms.ConfigureFTPForm(datasets = ds_list, cert_names = cert_name_list, initial=initial)
      return_dict['form'] = form
      return django.shortcuts.render_to_response('configure_ftp.html', return_dict, context_instance = django.template.context.RequestContext(request))
    else:
      form = ftp_management_forms.ConfigureFTPForm(request.POST, cert_names = cert_name_list, datasets = ds_list)
      return_dict['form'] = form
      if not form.is_valid():
        return django.shortcuts.render_to_response("configure_ftp.html", return_dict, context_instance = django.template.context.RequestContext(request))
      cd = form.cleaned_data
      ret, err = vsftp.update_ftp_config(cd)
      if err:
        raise Exception(err)
      users,err = local_users.get_local_users()
      if err:
        raise Exception(err)
      ret, err = vsftp.create_ftp_user_dirs(cd['dataset'], users)
      if err:
        raise Exception(err)
      audit_str = 'Updated FTP configuration.'
      if cd['ssl_enabled']:
        audit_str = audit_str + ' SSL enabled with certificate %s'%cd['cert_name']
      else:
        audit_str = audit_str + ' SSL disabled.'
      ret, err = audit.audit("update_ftp_config", audit_str, request.META["REMOTE_ADDR"])
      return django.http.HttpResponseRedirect('/view_ftp_configuration?action=saved')
  except Exception, e:
    return_dict['base_template'] = "services_base.html"
    return_dict["page_title"] = 'Configure FTP service'
    return_dict['tab'] = 'ftp_service_settings'
    return_dict["error"] = 'Error configuring the FTP service '
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))


def create_ftp_user_dirs(request):
  return_dict = {}
  try:
    config, err = vsftp.get_ftp_config()
    if err:
      raise Exception(err)
    if 'dataset' not in config:
      raise Exception('No home dataset has been configured for the FTP service. Please do that before creating FTP home directories')
    users, err = local_users.get_local_users()
    if err:
      raise Exception(err)
    res, err = vsftp.create_ftp_user_dirs(config['dataset'], users)
    if err:
      raise Exception(err)
    
    audit.audit("create_ftp_dir", 'Created FTP user directories', request.META["REMOTE_ADDR"])
    return django.http.HttpResponseRedirect('/view_ftp_configuration?action=dirs_created')
  
  except Exception, e:
    return_dict['base_template'] = "services_base.html"
    return_dict["page_title"] = 'Create FTP user directories'
    return_dict['tab'] = 'ftp_service_settings'
    return_dict["error"] = 'Error creating FTP user directories '
    return_dict["error_details"] = str(e)
    return django.shortcuts.render_to_response("logged_in_error.html", return_dict, context_instance=django.template.context.RequestContext(request))
