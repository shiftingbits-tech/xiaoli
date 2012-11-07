#!/usr/bin/env python 
# coding: utf-8

from flask import json
from flask import (Blueprint, request, url_for, redirect, render_template, flash)

from tango import db, cache, update_profile

from tango.ui import navbar
from tango.base import NestedDict
from tango.ui.tables import make_table
from tango.login import logout_user, login_user, current_user
from tango.models import Profile

from nodes.models import Area
from .models import User, Role, Permission, Domain
from .forms import (UserEditForm, UserNewForm, LoginForm, PasswordForm, RoleForm,
                    ProfileForm, DomainForm, ResetPasswordForm)
from .tables import UserTable, RoleTable, DomainTable

userview = Blueprint('users', __name__)

@userview.context_processor
def inject_navid():
    return dict(navid = 'users')

# ===============================================================================
#  Authenticating
# =============================================================================== 
@userview.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm(next=request.args.get('next', ''))
    if request.method == 'POST':
        username = form.username.data
        password = form.password.data
        next = form.next.data
        user, authenticated = User.authenticate(username, password)
        DEBUG = True # For DEBUG
        print 'DEBUG::', DEBUG
        if user and authenticated or DEBUG: 
            remember = (form.remember.data == 'y')
            if login_user(user, remember = remember):
                #flash(u'登录成功', 'success')
                if next:
                    return redirect(next)
                return redirect('/')
        elif not user:
            flash(u'用户不存在', 'error')
        else: 
            flash(u'密码错误', 'error')

        form.next.data = request.args.get('next', '')
    return render_template('login.html', form = form)

    
@userview.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect('/login')

    
# ==============================================================================
#  Setting
# ==============================================================================
@userview.route('/settings')
def settings():
    return redirect(url_for('users.user_info'))
    

@userview.route('/settings/profile', methods=['POST', 'GET'])
def profile():
    uid = current_user.id
    args = request.values
    update_profile(args['grp'], args['key'], args['value'])
    db.session.commit()
    if request.method == 'GET':
        return redirect(request.referrer)
    else:
        return 'Updated!'
        
    
@userview.route('/settings/info', methods=['POST', 'GET'])
def user_info():
    '''用户修改自己的个人信息'''
    
    form = ProfileForm()
    user = User.query.get_or_404(current_user.id)
    if request.method == 'POST' and form.validate_on_submit():
        form.populate_obj(user)
        db.session.commit()
        flash(u'个人信息修改成功', 'success')
        return redirect(url_for('users.user_info'))
    
    form.process(obj=user)
    form.role_name.data = user.role.name
    form.domain_name.data = user.domain.name
    return render_template('settings/user_info.html', form=form)

    
@userview.route('/settings/password', methods=['POST', 'GET'])
def change_password():
    '''用户修改自己的密码'''
    
    form = PasswordForm()
    if request.method == 'POST' and form.validate():
        user = User.query.get_or_404(current_user.id)
        if user.check_passwd(form.oldpasswd.data):
            user.password = form.newpasswd.data
            db.session.commit()
            flash(u"密码修改成功", 'success')
        else:
            flash(u'当前密码错误', 'error')
    return render_template("settings/password.html", form = form)

# ==============================================================================
#  User
# ==============================================================================
from tango.ui.queries import QueryForm, TextField, SelectField

class UserQueryForm(QueryForm):
    username  = TextField(u'用户名', operator='ilike')
    name      = TextField(u'真实姓名', operator='ilike')
    domain_id = SelectField(u'管理域', operator='==',
                            choices=lambda: [('', u'请选择')] + [(unicode(d.id), d.name) for d in Domain.query])
    role_id   = SelectField(u'角色名', operator='==',
                            choices=lambda: [('', u'请选择')] + [(unicode(r.id), r.name) for r in Role.query])

    class Meta():
        model = User

        
@userview.route('/users/')
def users():
    keyword = request.args.get('keyword', '')
    query = User.query
    if keyword:
        query = query.filter(db.or_(User.name.ilike('%' + keyword + '%'),
                                    User.email.ilike('%' + keyword + '%'),
                                    User.role.has(Role.name.ilike('%' + keyword + '%'))))        
    table = make_table(query, UserTable)
    return render_template('users/index.html', table=table, keyword=keyword)
    
@userview.route('/users/new', methods=['POST', 'GET'])
def users_new():
    form = UserNewForm()
    if request.method == 'POST' and form.validate_on_submit():
        username = form.username.data
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User()
            form.populate_obj(user)
            db.session.add(user)
            db.session.commit()
            flash(u'添加用户(%s)成功' % user.username, 'success')
            return redirect(url_for('users.users'))
    return render_template('users/new.html', form=form)


@userview.route('/t-modal/<int:id>', methods=['POST', 'GET'])
def test_modal(id):
    return render_template('users/test-modal%d.html' % id)
    
    
@userview.route('/users/edit/<int:id>', methods=['POST', 'GET'])
def users_edit(id):
    form = UserEditForm()
    user = User.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        form.populate_obj(user)
        db.session.add(user)
        db.session.commit()
        cache.delete("user-"+str(id))
        flash(u'修改用户(%s)成功' % user.username, 'success')
        return redirect(url_for('users.users'))
        
    form.process(obj=user)
    kwargs = {
        'title'  : u'编辑用户',
        'action' : url_for('users.users_edit', id=id),
        'form'   : form,
        'type'   : 'edit'
    }
    return render_template('_modal.html', **kwargs)

    
@userview.route('/users/delete/<int:id>', methods=('GET', 'POST'))
def users_delete(id):
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        db.session.delete(user)
        db.session.commit()
        cache.delete("user-"+str(id))
        flash(u'用户(%s)删除成功' % user.username, 'success')
        return redirect(url_for('users.users'))
        
    kwargs = {
        'title'  : u'删除用户',
        'action' : url_for('users.users_delete', id=id),
        'fields' : [(u'用户名', user.username), (u'真实姓名', user.name)],
        'type'   : 'delete'
    }
    return render_template('_modal.html', **kwargs)

    
@userview.route('/users/delete/all', methods=['GET', 'POST'])
def users_delete_all():
    if request.method == 'POST':
        ids = dict(request.values.lists()).get('id', [])
        for i in ids:
            cache.delete("user-"+str(i))
            db.session.delete(User.query.get(int(i)))
        db.session.commit()
        flash(u'成功删除 %d 个用户!' % len(ids) , 'success')
        return redirect(url_for('users.users'))

    ids = dict(request.values.lists()).get('id[]', [])
    users = User.query.filter(User.id.in_([int(i) for i in ids])).all()
    kwargs = {
        'title': u'批量删除用户',
        'action': url_for('users.users_delete_all'),
        'fields': [(u.id, u'用户名', u.username) for u in users],
        'type' : 'delete'
    }
    return render_template('_modal_del_all.html', **kwargs)

    
@userview.route('/users/reset-password/<int:id>', methods=['POST', 'GET'])
def reset_password(id):
    '''管理员重置用户密码'''
    
    form = ResetPasswordForm()
    user = User.query.get(id)
    if request.method == 'POST' and form.validate_on_submit():
        newpasswd = form.newpasswd.data
        user.password = newpasswd
        db.session.commit()
        flash(u'用户(%s)密码重置成功' % user.username , 'success')
        return redirect(url_for('users.users'))
        
    form.username.data = user.username
    return render_template('users/reset_password.html', form=form, user=user)



    
# ==============================================================================
#  Role
# ============================================================================== 
@userview.route('/roles/')
def roles():
    table = make_table(Role.query, RoleTable)
    return render_template('users/roles/index.html', table=table)
    
@userview.route('/roles/new', methods=['GET', 'POST'])
def roles_new():
    all_args = NestedDict(request)
    perms = all_args['permissions']
    form = RoleForm()
    role = Role()
    if request.method == 'POST' and form.validate_on_submit():
        for p in perms.keys():
            perm = Permission.query.get(int(p))
            role.permissions.append(perm)
            
        form.populate_obj(role)
        db.session.add(role)
        db.session.commit()
        flash(u'新建角色成功', 'success')
        return redirect(url_for('users.roles'))

    perm_tree = Permission.make_tree()
    
    return render_template('users/roles/new_edit.html',
                           action=url_for('users.roles_new'),
                           form=form, perm_tree=perm_tree)
    

@userview.route('/roles/edit/<int:id>', methods=['POST', 'GET'])
def roles_edit(id):
    all_args = NestedDict(request)
    perms = all_args['permissions']
    form = RoleForm()
    role = Role.query.get_or_404(id)
    
    if request.method == 'POST' and form.validate_on_submit():
        while len(role.permissions) > 0:
            role.permissions.pop(0)
        for p in perms:
            perm = Permission.query.get(int(p))
            role.permissions.append(perm)

        form.populate_obj(role)
        db.session.add(role)
        db.session.commit()
        flash(u'修改角色(%s)成功' % role.name, 'success')
        return redirect(url_for('users.roles'))
    
    perm_tree = Permission.make_tree(role.permissions)
    form.process(obj=role)
    return render_template('users/roles/new_edit.html',
                           action=url_for('users.roles_edit', id=id),
                           form=form, perm_tree=perm_tree)
    

@userview.route('/roles/delete/<int:id>', methods=('GET', 'POST'))
def roles_delete(id):
    user_cnt = User.query.filter(User.role_id == id).count()
    role = Role.query.get(id)
    if user_cnt > 0:
        flash(u'删除失败: 有(%d)个用户依赖此角色' % user_cnt, 'error')
    elif request.method == 'GET':
        return render_template('users/roles/delete.html', role=role)
    else:
        db.session.delete(role)
        db.session.commit()
        flash(u'删除角色(%s)成功' % role.name, 'success')
    return redirect(url_for('users.roles'))

    
# ==============================================================================
#  Domain
# ==============================================================================
@userview.route('/domains/')
def domains():
    table = make_table(Domain.query, DomainTable)
    return render_template('users/domains/index.html', table=table)
    
@userview.route('/domains/load/nodes')
def domain_load_nodes():
    key = request.args.get('key', '')
    domain_areas = request.args.get('domain_areas', '')
    domain_areas = [int(area_id) for area_id in domain_areas.split(',') if area_id]\
                   if domain_areas else []

    root = Area.query.filter(Area.area_type==0).first()
    areas = []
    if key:
        key = int(key)
    if domain_areas:
        areas = [Area.query.get(area_id) for area_id in domain_areas]
        
    path_nodes = set([root.id])
    if not key:
        for area in areas:
            while area.parent_id != -1:
                path_nodes.add(area.parent_id)
                area = Area.query.get(area.parent_id)

    def make_node(area):
        node = {}
        node['title'] = area.name
        node['key'] = str(area.id)
        if area.id in domain_areas:
            node['select'] = True
        if len(area.children) > 0:
            node['isLazy'] = True
        return node

    def make_nodes(area_id):
        area = Area.query.get(area_id)
        node = make_node(area)
        if len(area.children) > 0:
            node['expand'] = True
            node['children'] = []
            for child in area.children:
                if child.id in path_nodes:
                    node['children'].append(make_nodes(child.id))
                else:
                    child_node = make_node(child)
                    node['children'].append(child_node)
        return node
    nodes = [make_node(area) for area in Area.query.filter(Area.parent_id==key)] \
            if key else [make_nodes(root.id)]
    
    return json.dumps(nodes)    


@userview.route('/domains/new', methods=['POST', 'GET'])
def domains_new():
    form = DomainForm()
    if request.method == 'POST' and form.validate_on_submit():
        domain = Domain()
        form.populate_obj(domain)
        domain.dump_areas(request.form['domain_areas'])
        db.session.add(domain)
        db.session.commit()
        return redirect(url_for('users.domains'))
    return render_template('users/domains/new_edit.html',
                           action=url_for('users.domains_new'),
                           form=form)

    
@userview.route('/domains/edit/<int:id>', methods=['POST', 'GET'])
def domains_edit(id):
    form = DomainForm()
    domain = Domain.query.get_or_404(id)
    if request.method == 'POST' and form.validate_on_submit():
        form.populate_obj(domain)
        domain.dump_areas(request.form['domain_areas'])
        db.session.add(domain)
        db.session.commit()
        flash(u'管理域(%s)修改成功' % domain.name, 'success')
        return redirect(url_for('users.domains'))
    domain_areas = [domain.city_list, domain.town_list,domain.branch_list, domain.entrance_list]
    domain_areas = ','.join([d for d in domain_areas if d])
    form.process(obj=domain)
    return render_template('users/domains/new_edit.html',
                           action=url_for('users.domains_edit', id=id),
                           domain_areas=domain_areas, form=form)
    

@userview.route('/domains/delete/<int:id>', methods=('GET', 'POST'))
def domains_delete(id):
    user_cnt = User.query.filter(User.domain_id == id).count()
    domain = Domain.query.get_or_404(id)
    if user_cnt > 0:
        flash(u'删除失败: 有(%d)个用户依赖此管理域!' % user_cnt, 'error')
    elif request.method == 'GET':
        return render_template('users/domains/delete.html', domain=domain)        
    else:
        db.session.delete(domain)
        db.session.commit()
        flash(u'管理域(%s)删除成功' % domain.name, 'success')
    return redirect(url_for('users.domains'))
    

# ==============================================================================
#  [OTHER]
# ==============================================================================
navbar.add('users', u'用户', 'user', '/users/')

@userview.route('/just-test/<name>/')
def just_test(name='a'):
    print '\n'.join([item for item in dir(request) if item.find('__') == -1])
    args =  request.args.to_dict()
    args.update(request.view_args)
    print args
    return name

@userview.route('/test-modal')
def test_modal():
    return render_template('users/test_modal.html')

